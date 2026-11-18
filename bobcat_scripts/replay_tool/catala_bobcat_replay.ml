(* Concrete replay against BOBCat's exact outcome manifest. Keep the hook in
   sync with compiler/bobcat/interpreter.ml:replay_model. No solver is run. *)
open Catala_utils
open Shared_ast
open Op

let position_id pos =
  Printf.sprintf "%s:%d:%d-%d:%d" (Pos.get_file pos)
    (Pos.get_start_line pos) (Pos.get_start_column pos)
    (Pos.get_end_line pos) (Pos.get_end_column pos)

let outcome_key tag pos =
  match tag with
  | Branching _ -> "branch@" ^ position_id pos
  | Exception { cons_pos; _ } ->
    "default@" ^ position_id pos ^ "=>" ^ position_id cons_pos
  | _ -> ""

let run includes stdlib scope input_file manifest_file output_name options =
  ignore (Global.enforce_options
    ~trace:(Some (lazy Format.str_formatter)) ());
  let prg, _ =
    Driver.Passes.dcalc options ~includes ~stdlib ~optimize:false
      ~check_invariants:false ~autotest:false ~typed:Expr.typed
  in
  Interpreter.load_runtime_modules
    ~hashf:Hash.(finalise ~monomorphize_types:false) prg;
  let scope = Driver.Commands.get_scope_uid prg.decl_ctx scope in
  let pairs = Hashtbl.create 257 in
  let manifest = match manifest_file with
    | Some file -> Yojson.Safe.from_file file
    | None ->
      let module C = Coverage_inventory in
      let definitions, entry = C.expose_entry_scope (Program.to_expr prg scope |> Expr.unbox) in
      let definitions = List.fold_left (fun env (v, e) -> Var.Map.add v e env)
        Var.Map.empty definitions in
      let body = match Mark.remove entry with
        | EAbs { binder; _ } -> snd (Bindlib.unmbind binder)
        | _ -> failwith "entry scope is not a function" in
      let body = C.select_output prg.decl_ctx definitions output_name body in
      let ctx = C.make_context () in
      C.index_source_branches ~definitions ctx body;
      let entries = Hashtbl.fold (fun _ pair entries -> pair :: entries)
        ctx.ctx_branch_pairs [] |> List.sort_uniq String.compare in
      `List (List.map (fun pair -> `String pair) entries)
  in
  match input_file with
  | None -> Format.printf "%s@." (Yojson.Safe.to_string manifest)
  | Some input_file ->
  (match manifest with
  | `List entries -> List.iter (function
      | `String pair ->
        (* Only the final slash separates decision and outcome; positions
           themselves may contain directory separators. Find the marker. *)
        let rec find i =
          if i < 0 then failwith ("invalid BOBCat outcome: " ^ pair)
          else if String.starts_with ~prefix:"/branch@"
                    (String.sub pair i (String.length pair - i))
               || String.starts_with ~prefix:"/default@"
                    (String.sub pair i (String.length pair - i))
          then i + 1 else find (i - 1)
        in
        let start = find (String.length pair - 1) in
        Hashtbl.replace pairs
          (String.sub pair start (String.length pair - start)) pair
      | _ -> failwith "non-string BOBCat outcome") entries
  | _ -> failwith "expected BOBCat outcome array");
  let hits = Hashtbl.create 32 in
  let record tag pos =
    Option.iter (fun pair -> Hashtbl.replace hits pair ())
      (Hashtbl.find_opt pairs (outcome_key tag pos))
  in
  let on_result original result =
    match Mark.remove original with
    | EAppOp { op = Tag ((Branching _ | Exception _) as tag), _; _ } ->
      (match tag, Mark.remove result with
      | Branching _, _ | Exception _, ELit (LBool true) ->
        record tag (Expr.pos original)
      | _ -> ())
    | EApp { f = ((EAbs _, _) as arm); _ } ->
      record (Branching None) (Expr.pos arm)
    | _ -> ()
  in
  let outputs = Interpreter.interpret_program_dcalc
    ~input:(Yojson.Safe.from_file input_file) ~on_result
    ~raise_on_error:true ~disable_trace:true prg scope in
  let branches = Hashtbl.fold (fun pair () acc -> pair :: acc) hits []
    |> List.sort String.compare in
  let output = `Assoc (List.map (fun ((name, _), value) ->
    name, `String (Format.asprintf "%a" (Print.expr ()) value)) outputs) in
  Format.printf "%s@." (Yojson.Safe.to_string (`Assoc [
    "branches", `List (List.map (fun pair -> `String pair) branches);
    "outputs", output]));
  Format.pp_print_flush Format.std_formatter ()

let file_flag name =
  Cmdliner.Arg.(value & opt (some string) None & info [name])

let term =
  let open Cmdliner.Term in
  const run $ Cli.Flags.include_dirs $ Cli.Flags.stdlib_dir $ Cli.Flags.ex_scope
  $ file_flag "replay-input" $ file_flag "replay-manifest"
  $ file_flag "coverage-output"

let () = Driver.Plugin.register "bobcat-replay" term
  ~doc:"Catalog source outcomes or concretely replay JSON inputs, without symbolic solving."
