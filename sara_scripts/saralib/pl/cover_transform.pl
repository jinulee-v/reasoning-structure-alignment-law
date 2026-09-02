% Rewrite one SARA statute file so that every body goal position records that
% it was reached.  Used by `saralib.coverage`; the apparatus is described in sara_scripts/README.md.
%
%   swipl saralib/pl/cover_transform.pl -- <in.pl> <out.pl> <file-tag>
%
% Every goal position gets two points: `c` when the goal is called, and `f`
% when it is called and has no solution.  A goal G becomes
%
%     cov('...:c'), ( G *-> true ; cov('...:f'), fail )
%
% so branch coverage -- every decision taken both ways -- is what gets counted,
% not merely which goals were reached.  The soft cut is what makes this
% transparent: `( G *-> true ; fail )` has exactly G's solutions in exactly G's
% order, where `->` would have committed to the first one.  A cut is left
% unwrapped, since `!` inside `*->` would cut the wrapper instead of the clause.
%
% Recursion goes through the control constructs (`,` `;` `->` `*->` `\+`) but
% not into meta-arguments: a goal inside findall/3 is reached through its own
% predicate's clauses, which carry their own points.
%
% `cov/1` always succeeds deterministically and binds nothing, so the
% transformed program has the same solutions in the same order as the original.
% That claim is checked, not assumed: `generate_test_cases.py` re-runs SARA's
% own cases against the instrumented copy and must reproduce their upstream
% verdicts before it generates anything.

:- initialization(main, main).

main([In, Out, Tag]) :-
    setup_call_cleanup(
        open(In, read, S),
        setup_call_cleanup(
            open(Out, write, O),
            ( format(O, ":- ~q.~n", [ensure_loaded(cov_runtime)]),
              process(S, O, Tag, 0, N) ),
            close(O)),
        close(S)),
    format("~w: ~d clauses~n", [Tag, N]).

process(S, O, Tag, N0, N) :-
    read_term(S, T, [term_position(Pos)]),
    (   T == end_of_file
    ->  N = N0
    ;   stream_position_data(line_count, Pos, Line),
        (   T = (:- D)
        ->  format(O, ":- ~q.~n", [D]), N1 = N0
        ;   N1 is N0 + 1,
            instrument(T, Tag, Line, T2),
            portray_clause(O, T2)
        ),
        process(S, O, Tag, N1, N)
    ).

instrument((H :- B), Tag, Line, (H :- B2)) :- !,
    instr(B, Tag, Line, 0, P, B1),
    point(Tag, Line, P, e, End),
    B2 = (B1, cov(End)).
instrument(H, Tag, Line, (H :- cov(P))) :-
    point(Tag, Line, 0, e, P).

instr(V, Tag, Line, P0, P, Out) :-
    var(V), !, wrap(call(V), Tag, Line, P0, P, Out).
instr((A, B), Tag, Line, P0, P, (A2, B2)) :- !,
    instr(A, Tag, Line, P0, P1, A2), instr(B, Tag, Line, P1, P, B2).
instr((A ; B), Tag, Line, P0, P, (A2 ; B2)) :- !,
    instr(A, Tag, Line, P0, P1, A2), instr(B, Tag, Line, P1, P, B2).
instr((A -> B), Tag, Line, P0, P, (A2 -> B2)) :- !,
    instr(A, Tag, Line, P0, P1, A2), instr(B, Tag, Line, P1, P, B2).
instr((A *-> B), Tag, Line, P0, P, (A2 *-> B2)) :- !,
    instr(A, Tag, Line, P0, P1, A2), instr(B, Tag, Line, P1, P, B2).
instr(\+ A, Tag, Line, P0, P, \+ A2) :- !,
    instr(A, Tag, Line, P0, P, A2).
instr(!, Tag, Line, P0, P, (cov(Pc), !)) :- !,
    point(Tag, Line, P0, c, Pc), P is P0 + 1.
instr(G, Tag, Line, P0, P, Out) :-
    wrap(G, Tag, Line, P0, P, Out).

wrap(G, Tag, Line, P0, P, (cov(Pc), ( G *-> true ; cov(Pf), fail ))) :-
    point(Tag, Line, P0, c, Pc),
    point(Tag, Line, P0, f, Pf),
    P is P0 + 1.

point(Tag, Line, P, Kind, Atom) :-
    format(atom(Atom), "~w:~d:~d:~w", [Tag, Line, P, Kind]).
