% main/0 for a *value probe*, not a verdict.
%
% `strengthen_goals` renders a case whose goal carries `'$probe'(I, Literal)`
% at every argument position holding a literal.  For each such position this
% frees that one argument, leaves the others at their literals, and reports
% every value SARA derives for it:
%
%     PROBE 2 [186242]        the world determines this argument
%     PROBE 1 '$err'          freeing it raises -- an input, not an output
%     PROBE 0 []              no solution -- nothing to bind
%
% A position that raises is how an unbound *year* announces itself:
% `first_day_year/2` is `atom_string/2`, which is an instantiation error rather
% than a failure (D12).  So the three outcomes separate outputs from inputs
% without anyone having to declare which is which.

:- use_module(library(time)).

main :-
    ( getenv('SARA_LIMIT', LS), atom_number(LS, L) -> true ; L = 30 ),
    sara_goal(G0),
    G0 =.. [_|Args0],
    findall(I, (nth0(I, Args0, A), nonvar(A), A = '$probe'(_, _)), Is),
    forall(member(I, Is), probe(G0, I, L)).

probe(G0, I, L) :-
    G0 =.. [Name|Args0],
    maplist(unmark, Args0, Args1),
    nth0(I, Args1, _, Rest),
    nth0(I, Args, V, Rest),
    G =.. [Name|Args],
    % `ground(V)` matters: a goal can succeed *without* binding the argument.
    % `latest/2` and `earliest/2` leave their output unbound on an empty list,
    % which callers read as "no constraint", and `findall` then collects a
    % fresh variable.  Writing that back into the goal yields the literal
    % `_35856`, which is not a value at all.
    (   catch(call_with_time_limit(L, findall(V, (G, ground(V)), Vs)),
              _, Vs = '$err')
    ->  true
    ;   Vs = '$err' ),
    format("PROBE ~w ~q~n", [I, Vs]).

unmark('$probe'(_, Lit), Lit) :- !.
unmark(X, X).
