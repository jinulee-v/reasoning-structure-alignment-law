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

let read_hex_lines () =
  let cov = ref Shared_ast.Coverage.empty in
  (try
     while true do
       let line = Stdlib.String.trim (input_line stdin) in
       let hex =
         match Stdlib.String.rindex_opt line '|' with
         | Some i ->
           Stdlib.String.trim
             (Stdlib.String.sub line (i + 1) (Stdlib.String.length line - i - 1))
         | None -> line
       in
       if hex <> "" then
         cov := Shared_ast.Coverage.union !cov (Shared_ast.Coverage.of_hex hex)
     done
   with End_of_file -> ());
  !cov

let () =
  let cov = read_hex_lines () in
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
      Buffer.add_string buf
        (Printf.sprintf "%s\t%d\t%d\t%d\t%d\t%d\t%s\n" file
           itv.Shared_ast.Coverage.start_line
           itv.Shared_ast.Coverage.start_col
           itv.Shared_ast.Coverage.end_line
           itv.Shared_ast.Coverage.end_col
           reached
           (Stdlib.String.concat "," scopes)))
    cov ();
  print_string (Buffer.contents buf)
