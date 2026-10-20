(* Enumerate the decision outcomes of a Catala program.

   `catala interpret --code-coverage` reports which source *positions* were
   evaluated.  That is statement coverage; on its own it cannot say whether an
   `if` went both ways.  This plugin supplies the missing half: it walks the
   same dcalc program, finds every decision, and prints the source position
   that is reached exactly when each outcome is taken.  Joining the two says
   which branches a suite took.

   The mapping holds because the interpreter's coverage hook marks
   `Expr.pos e` for every expression it evaluates:

     EIfThenElse   `etrue` and `efalse` are evaluated only on their own side.
     EMatch        an arm's body is evaluated only when that constructor
                   matched.  Arms are lambdas over the payload, so the position
                   wanted is the lambda's *body* --- `reachable_positions`
                   skips the lambda's own position for the same reason.
     EDefault      `cons` is evaluated only once `just` came out true, so a
                   consequence's position is reached exactly when that
                   alternative fired.

   Defaults need care, because one rule with one exception compiles to four
   nested EDefaults, two of which are scaffolding.  `definition reduction
   equals $0` with `exception ... under condition applies` becomes

     D0 ⟨ D1 | true ⊢ D2 ⟩         group root
     D1 ⟨ D3 | false ⊢ ∅ ⟩         exception-group wrapper
     D2 ⟨      true ⊢ ⟨$0⟩ ⟩       the base alternative
     D3 ⟨   applies ⊢ ⟨min …⟩ ⟩    the exception

   The alternatives that carry law are the *leaves* --- `excepts = []` with a
   consequence that is not `∅`.  D0 and D1 hold no body and are emitted only as
   the group identity, so that a report can say which alternatives compete for
   the same variable.  `guarded` distinguishes D3 (`just` is a real condition)
   from D2 (`just` is literally true, so it fires whenever no exception did).

   Output is one TSV row per outcome, so nothing but the join needs to know
   about Catala:

     kind  outcome  guarded  gfile gsl gsc gel gec  ofile osl osc oel oec

   with `g…` the position identifying the decision --- an `if`, a `match`, or a
   default group --- and `o…` the outcome's own. *)

open Catala_utils
open Shared_ast

let pos_cols pos =
  Printf.sprintf "%s\t%d\t%d\t%d\t%d" (Pos.get_file pos) (Pos.get_start_line pos)
    (Pos.get_start_column pos) (Pos.get_end_line pos) (Pos.get_end_column pos)

let row buf ~kind ~outcome ~guarded ~group ~pos =
  Buffer.add_string buf
    (Printf.sprintf "%s\t%s\t%b\t%s\t%s\n" kind outcome guarded (pos_cols group)
       (pos_cols pos))

(* Where an arm's body will be marked.  Arms are `EAbs` over the payload; the
   interpreter never marks the lambda itself. *)
let rec body_pos e =
  match Mark.remove e with
  | EAbs { binder; _ } ->
    let _, e' = Bindlib.unmbind binder in
    body_pos e'
  | _ -> Expr.pos e

let is_literally_true e =
  match Mark.remove e with ELit (LBool true) -> true | _ -> false

let is_empty e = match Mark.remove e with EEmpty -> true | _ -> false

let collect_expr buf e =
  (* [group] is the position of the outermost default of the group currently
     being walked, so that competing alternatives report the same identity. *)
  let rec loop ?group e =
    match Mark.remove e with
    | EDefault { excepts; just; cons } ->
      let g = match group with Some g -> g | None -> Expr.pos e in
      List.iter (loop ~group:g) excepts;
      loop just;
      if excepts = [] && not (is_empty cons) then begin
        row buf ~kind:"default"
          ~outcome:(if is_literally_true just then "base" else "exception")
          ~guarded:(not (is_literally_true just))
          ~group:g ~pos:(Expr.pos cons);
        loop cons
      end
      else if not (is_empty cons) then loop ~group:g cons
    | EIfThenElse { cond; etrue; efalse } ->
      let g = Expr.pos e in
      loop cond;
      row buf ~kind:"if" ~outcome:"then" ~guarded:true ~group:g
        ~pos:(Expr.pos etrue);
      row buf ~kind:"if" ~outcome:"else" ~guarded:true ~group:g
        ~pos:(Expr.pos efalse);
      loop etrue;
      loop efalse
    | EMatch { name; e = scrutinee; cases } ->
      let g = Expr.pos e in
      loop scrutinee;
      EnumConstructor.Map.iter
        (fun cons body ->
          row buf ~kind:"match"
            ~outcome:
              (Format.asprintf "%a.%a" EnumName.format name
                 EnumConstructor.format cons)
            ~guarded:true ~group:g ~pos:(body_pos body);
          loop body)
        cases
    | EAbs { binder; _ } ->
      let _, e' = Bindlib.unmbind binder in
      loop e'
    | _ -> Expr.shallow_fold (fun sub () -> loop sub) e ()
  in
  loop e

let run includes stdlib output optimize check_invariants options =
  let prg, _ =
    Driver.Passes.dcalc options ~includes ~stdlib ~optimize ~check_invariants
      ~autotest:false ~typed:Expr.typed
  in
  let buf = Buffer.create 65536 in
  Program.fold_exprs ~init:() ~f:(fun () e _typ -> collect_expr buf e) prg;
  Driver.Commands.get_output_format options ~ext:"branches.tsv" output
  @@ fun _ fmt ->
  Format.fprintf fmt
    "kind\toutcome\tguarded\tgfile\tgsl\tgsc\tgel\tgec\tofile\tosl\tosc\toel\toec\n";
  Format.pp_print_string fmt (Buffer.contents buf)

let term =
  let open Cmdliner.Term in
  const run
  $ Cli.Flags.include_dirs
  $ Cli.Flags.stdlib_dir
  $ Cli.Flags.output
  $ Cli.Flags.optimize
  $ Cli.Flags.check_invariants

let () =
  Driver.Plugin.register "branches" term
    ~doc:
      "Print every decision outcome in the program, with the source position \
       that is reached exactly when that outcome is taken."
