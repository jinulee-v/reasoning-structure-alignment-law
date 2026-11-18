(* This file is part of the Catala compiler, a specification language for tax
   and social benefits computation rules. Copyright (C) 2020 Inria, contributor:
   Denis Merigoux <denis.merigoux@inria.fr>, Emile Rolley
   <emile.rolley@tuta.io>, Alain Delaët <alain.delaet--tixeuil@inria.Fr>, Louis
   Gesbert <louis.gesbert@inria.fr>

   Licensed under the Apache License, Version 2.0 (the "License"); you may not
   use this file except in compliance with the License. You may obtain a copy of
   the License at

   http://www.apache.org/licenses/LICENSE-2.0

   Unless required by applicable law or agreed to in writing, software
   distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
   WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
   License for the specific language governing permissions and limitations under
   the License. *)

(* Static coverage catalog adapted from BOBCat indexing; no solver or input generation. *)
open Catala_utils
open Shared_ast
open Op

type context = {
  ctx_branch_pairs : (string, string) Hashtbl.t;
}

let make_context () = { ctx_branch_pairs = Hashtbl.create 257 }

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

let decision_id kind pos = kind ^ "@" ^ position_id pos

let rec demanded_struct_field definitions seen field e =
  match Mark.remove e with
  | EStruct { fields; _ } -> StructField.Map.find_opt field fields
  | EVar var when not (Var.Set.mem var seen) ->
    Option.bind (Var.Map.find_opt var definitions)
      (demanded_struct_field definitions (Var.Set.add var seen) field)
  | EApp { f; args; _ } ->
    let rec callable seen f =
      match Mark.remove f with
      | EVar var when not (Var.Set.mem var seen) ->
        Option.fold ~none:f ~some:(callable (Var.Set.add var seen))
          (Var.Map.find_opt var definitions)
      | EAppOp { op = Tag _, _; args = [inner]; _ } -> callable seen inner
      | _ -> f
    in
    begin match Mark.remove (callable seen f) with
    | EAbs { binder; _ }
      when Bindlib.mbinder_arity binder = List.length args ->
      Bindlib.msubst binder (Array.of_list (List.map Mark.remove args))
      |> demanded_struct_field definitions seen field
    | _ -> None
    end
  | EAppOp { op = Tag _, _; args = [inner]; _ } ->
    demanded_struct_field definitions seen field inner
  | _ -> None

let index_source_branches ?(definitions = Var.Map.empty)
    ?(objective_depths = Hashtbl.create 257) ctx root =
  Hashtbl.clear ctx.ctx_branch_pairs;
  let decision_by_pair = Hashtbl.create 257 in
  let outcomes_by_decision = Hashtbl.create 257 in
  let visited_definitions = ref Var.Map.empty in
  let decision_depths = Hashtbl.create 257 in
  let record_depth table key depth =
    match Hashtbl.find_opt table key with
    | Some previous when previous <= depth -> ()
    | _ -> Hashtbl.replace table key depth
  in
  let register_outcome decision outcome =
    let pair = decision ^ "/" ^ outcome in
    Hashtbl.replace ctx.ctx_branch_pairs outcome pair;
    Hashtbl.replace decision_by_pair pair decision;
    Option.iter (record_depth objective_depths pair)
      (Hashtbl.find_opt decision_depths decision);
    let outcomes =
      Option.value ~default:[]
        (Hashtbl.find_opt outcomes_by_decision decision)
    in
    Hashtbl.replace outcomes_by_decision decision (pair :: outcomes)
  in
  let rec walk current_decision depth e =
    match Mark.remove e with
    | EVar var ->
      begin match Var.Map.find_opt var definitions with
      | Some definition when
          (match Var.Map.find_opt var !visited_definitions with
           | None -> true | Some previous -> depth < previous) ->
        visited_definitions := Var.Map.add var depth !visited_definitions;
        walk None depth definition
      | _ -> ()
      end
    | EIfThenElse { cond; etrue; efalse } ->
      let decision = decision_id "if" (Expr.pos e) in
      record_depth decision_depths decision depth;
      walk None (depth + 1) cond;
      walk (Some decision) (depth + 1) etrue;
      walk (Some decision) (depth + 1) efalse
    | EMatch { e = subject; cases; _ } ->
      let decision = decision_id "match" (Expr.pos e) in
      record_depth decision_depths decision depth;
      walk None (depth + 1) subject;
      EnumConstructor.Map.iter
        (fun _ arm ->
          register_outcome decision ("branch@" ^ position_id (Expr.pos arm));
          walk None (depth + 1) arm)
        cases
    | EDefault { excepts; just; cons } ->
      let current =
        if List.length excepts >= 1 then begin
          let decision = decision_id "default" (Expr.pos e) in
          record_depth decision_depths decision depth;
          Some decision
        end
        else current_decision
      in
      let child_depth = if excepts = [] then depth else depth + 1 in
      List.iter (walk current child_depth) excepts;
      walk current child_depth just;
      walk current child_depth cons
    | EAppOp { op = Tag tag, _; args = [inner]; _ } ->
      begin match tag, current_decision with
      | (Branching _ | Exception _), Some decision ->
        register_outcome decision (outcome_key tag (Expr.pos e))
      | _ -> ()
      end;
      walk None depth inner
    | _ ->
      Expr.shallow_fold
        (fun child () -> walk current_decision depth child) e ()
  in
  walk None 0 root;
  Hashtbl.filter_map_inplace
    (fun _ pair ->
      match Hashtbl.find_opt decision_by_pair pair with
      | None -> None
      | Some decision ->
        let outcomes =
          Option.value ~default:[]
            (Hashtbl.find_opt outcomes_by_decision decision)
          |> List.sort_uniq String.compare
        in
        if List.length outcomes >= 2 then Some pair else None)
    ctx.ctx_branch_pairs

exception Unsupported_goal of string

let expose_entry_scope (program : typed Dcalc.Ast.expr) =
  let rec expose definitions seen (e : typed Dcalc.Ast.expr) =
    match Mark.remove e with
    | EApp { f = (EAbs { binder; _ }, _); args; _ }
      when Bindlib.mbinder_arity binder = List.length args ->
      let vars, body = Bindlib.unmbind binder in
      let definitions =
        List.fold_left2
          (fun definitions var definition ->
            Var.Map.add var definition definitions)
          definitions (Array.to_list vars) args
      in
      expose definitions seen body
    | EVar var ->
      if Var.Set.mem var seen then
        raise (Unsupported_goal "cyclic top-level definition while locating scope")
      else
        begin match Var.Map.find_opt var definitions with
        | Some definition ->
          expose definitions (Var.Set.add var seen) definition
        | None ->
          raise
            (Unsupported_goal
               "unbound top-level variable while locating entry scope")
        end
    | EAbs _ -> Var.Map.bindings definitions, e
    | _ ->
      raise
        (Unsupported_goal
           "the compiled entry scope is not a function after lazy unfolding")
  in
  expose Var.Map.empty Var.Set.empty program


let select_output (decl_ctx : decl_ctx) definitions requested
    (body : typed Dcalc.Ast.expr) =
  match requested with
  | None -> body
  | Some requested ->
    begin match Mark.remove (Shared_ast.Expr.ty body) with
    | TStruct name ->
      let fields = StructName.Map.find name decl_ctx.ctx_structs in
      let selected =
        StructField.Map.bindings fields
        |> List.find_opt (fun (field, _) ->
             String.equal requested (StructField.original_string field))
      in
      begin match selected with
      | Some (field, ty) ->
        Option.value
          ~default:
            (Expr.estructaccess ~name ~field ~e:(Expr.box body)
               (Expr.with_ty (Mark.get body) ty)
             |> Expr.unbox)
          (demanded_struct_field definitions Var.Set.empty field body)
      | None ->
        raise
          (Unsupported_goal
             (Printf.sprintf "scope output %S does not exist" requested))
      end
    | _ ->
      raise
        (Unsupported_goal
           "the entry scope does not return an output structure")
    end
