(* Union a set of Catala coverage dumps and print them as one record per
   position.

   `catala interpret --code-coverage --quiet` ends its line with
   `Scope: passed|<hex>`, where the hex is a marshalled
   `Shared_ast.Coverage.coverage_map`.  Nothing outside the compiler can read
   that --- it is an OCaml value, not a format --- and a suite's coverage is the
   union over its runs, so the union has to happen here, on this side of the
   marshalling, and only the result crosses over into Python.

   Reads those lines on stdin, writes one tab-separated record per position:

       file  start_line  start_col  end_line  end_col  reached  scopes

   `reached` is 0 or 1 and `scopes` is a comma-separated list of the scopes that
   reached it.  A position that appears with `reached = 0` is one the program
   contains and the suite never ran: those are the denominator. *)

let hex_of_line line =
  let line = Stdlib.String.trim line in
  match Stdlib.String.rindex_opt line '|' with
  | Some i ->
    Stdlib.String.trim
      (Stdlib.String.sub line (i + 1) (Stdlib.String.length line - i - 1))
  | None -> line

let read_hex_lines () =
  let cov = ref Shared_ast.Coverage.empty in
  (try
     while true do
       let hex = hex_of_line (input_line stdin) in
       if hex <> "" then
         cov := Shared_ast.Coverage.union !cov (Shared_ast.Coverage.of_hex hex)
     done
   with End_of_file -> ());
  !cov

let position_key file itv =
  Printf.sprintf "%s\t%d\t%d\t%d\t%d" file
    itv.Shared_ast.Coverage.start_line itv.Shared_ast.Coverage.start_col
    itv.Shared_ast.Coverage.end_line itv.Shared_ast.Coverage.end_col

let print_cov ?(reached_only = false) cov =
  let buf = Buffer.create 65536 in
  Shared_ast.Coverage.fold
    (fun (file, itv) cover () ->
      let reached, scopes =
        match cover with
        | Shared_ast.Coverage.Unreached -> 0, []
        | Shared_ast.Coverage.Reached_by { scopes } ->
          ( 1,
            List.map Shared_ast.ScopeName.to_string
              (Shared_ast.Coverage.ScopeSet.elements scopes) )
      in
      if (not reached_only) || reached = 1 then
        Buffer.add_string buf
          (Printf.sprintf "%s\t%d\t%d\t%d\t%d\t%d\t%s\n" file
             itv.Shared_ast.Coverage.start_line
             itv.Shared_ast.Coverage.start_col
             itv.Shared_ast.Coverage.end_line
             itv.Shared_ast.Coverage.end_col reached
             (Stdlib.String.concat "," scopes)))
    cov ();
  print_string (Buffer.contents buf)

let print_each () =
  let index = ref 0 in
  (try
     while true do
       let hex = hex_of_line (input_line stdin) in
       if hex <> "" then (
         Printf.printf "@%d\n" !index;
         print_cov ~reached_only:true (Shared_ast.Coverage.of_hex hex);
         flush stdout;
         incr index)
     done
   with End_of_file -> ())

let read_catalog path =
  let catalog = Hashtbl.create 4096 in
  let channel = open_in path in
  (try
     while true do
       let line = input_line channel in
       match Stdlib.String.index_opt line '\t' with
       | None -> ()
       | Some i ->
         let id = int_of_string (Stdlib.String.sub line 0 i) in
         let key =
           Stdlib.String.sub line (i + 1) (Stdlib.String.length line - i - 1)
         in
         Hashtbl.replace catalog key id
     done
   with End_of_file -> close_in channel);
  catalog

let print_catalog path =
  let catalog = read_catalog path in
  (try
     while true do
       let hex = hex_of_line (input_line stdin) in
       if hex <> "" then (
         let first = ref true in
         Shared_ast.Coverage.fold
           (fun (file, itv) cover () ->
             match cover with
             | Shared_ast.Coverage.Unreached -> ()
             | Shared_ast.Coverage.Reached_by _ -> (
               match Hashtbl.find_opt catalog (position_key file itv) with
               | None -> ()
               | Some id ->
                 if not !first then print_char ',';
                 print_int id;
                 first := false))
           (Shared_ast.Coverage.of_hex hex) ();
         print_newline ();
         flush stdout)
     done
   with End_of_file -> ())

let () =
  match Array.to_list Sys.argv with
  | [_; "--each"] -> print_each ()
  | [_; "--catalog"; path] -> print_catalog path
  | _ -> read_hex_lines () |> print_cov
