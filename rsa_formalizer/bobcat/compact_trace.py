"""Project runtime traces onto annotated scopes without losing dependencies."""
from pathlib import Path
from .trace import _definition_blocks

FORMAT = 'xml_scopes_projected_dependencies_v1'


def annotated_scopes(snapshot: Path) -> list[str]:
    return sorted({scope for scope, _ in _definition_blocks(snapshot)})


def ocaml_projection(scopes: list[str]) -> str:
    import json
    names = '; '.join(json.dumps(name) for name in scopes)
    return r'''
let rsa_project_trace events =
  let open Catala_runtime in
  let scopes = [''' + names + r'''] in
  let scope_name name =
    match List.rev (String.split_on_char ':' name) with
    | name :: _ -> name
    | [] -> name in
  let keep_info = function
    | name :: _ -> List.mem (scope_name name) scopes
    | [] -> false in
  let frontiers = Hashtbl.create 1024 in
  let expand reads =
    let seen = Hashtbl.create 16 in
    let output = ref [] in
    List.iter (fun read ->
      let inherited = match Hashtbl.find_opt frontiers read.definition_id with
        | Some [single] when single.definition_id = read.definition_id -> [read]
        | Some values -> values
        | None -> failwith "trace dependency has no earlier definition" in
      List.iter (fun dependency ->
        let key = (dependency.definition_id, dependency.field) in
        if not (Hashtbl.mem seen key) then begin
          Hashtbl.add seen key ();
          output := dependency :: !output
        end) inherited) reads;
    List.rev !output in
  let calls = ref [] in
  let output = ref [] in
  List.iter (function
    | BeginCall info as event ->
        let keep = keep_info info in
        calls := keep :: !calls;
        if keep then output := event :: !output
    | EndCall _ as event ->
        (match !calls with
        | keep :: rest -> calls := rest; if keep then output := event :: !output
        | [] -> failwith "unbalanced runtime trace")
    | VariableDefinition (info, io, value, id, reads) ->
        let dependencies = expand reads in
        if keep_info info then begin
          Hashtbl.replace frontiers id [{definition_id=id; field=None}];
          output := VariableDefinition (info, io, value, id, dependencies) :: !output
        end else Hashtbl.replace frontiers id dependencies
    | (DecisionTaken _ | BranchTaken _) as event ->
        (match !calls with
        | true :: _ -> output := event :: !output
        | _ -> ())) events;
  if !calls <> [] then failwith "unclosed runtime trace";
  List.rev !output
'''
