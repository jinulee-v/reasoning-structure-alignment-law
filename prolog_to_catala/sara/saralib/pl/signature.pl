% Extract, from the SARA statutes themselves, two things the fuzzer currently
% guesses at:
%
%   edges    -- the call graph, so the *relevant input signature* of a query
%               predicate is the set of event predicates reachable from it
%               rather than all 53;
%   literals -- every constant the statutes compare a fact argument against,
%               tagged with the predicate and position it appears in, so the
%               value dictionary is derived from the program instead of from
%               SARA's corpus.
%
%   swipl saralib/pl/signature.pl -- <statutes-dir> <out.json>

:- initialization(main, main).
:- use_module(library(json)).

main([Dir, Out]) :-
    atom_concat(Dir, '/*.pl', Pattern),
    expand_file_name(Pattern, Files),
    retractall(edge(_, _)), retractall(lit(_, _, _)),
    forall(member(F, Files), scan(F)),
    findall(_{from: A, to: B}, edge(A, B), Edges0), sort(Edges0, Edges),
    findall(_{pred: P, pos: I, value: V}, lit(P, I, V), Lits0), sort(Lits0, Lits),
    setup_call_cleanup(open(Out, write, S),
        json_write_dict(S, _{edges: Edges, literals: Lits}),
        close(S)),
    length(Edges, NE), length(Lits, NL),
    format("~d edges, ~d literal positions~n", [NE, NL]).

:- dynamic edge/2.
:- dynamic lit/3.

scan(File) :-
    file_base_name(File, Base),
    \+ memberchk(Base, ['events.pl', 'init.pl', 'cov_runtime.pl']),
    !,
    setup_call_cleanup(open(File, read, S), read_all(S), close(S)).
scan(_).

read_all(S) :-
    read_term(S, T, []),
    (   T == end_of_file
    ->  true
    ;   ( clause_parts(T, H, B) -> record(H, B) ; true ),
        read_all(S)
    ).

clause_parts((H :- B), H, B) :- !.
clause_parts(H, H, true) :- H \= (:- _).

record(H, B) :-
    key(H, HK),
    forall(body_goal(B, G), ( key(G, GK), assertz_new(edge(HK, GK)), args(G) )).

assertz_new(E) :- ( E -> true ; assertz(E) ).

% `s3306_a_4()` really does appear in section3306.pl: a zero-argument compound,
% which functor/3 refuses, so name and arity are taken the safe way.
key(G, K) :-
    (   atom(G) -> N = G, A = 0
    ;   compound_name_arity(G, N, A) ),
    format(atom(K), "~w/~w", [N, A]).

% Every goal in a clause body, through the control constructs and through the
% meta-arguments of the aggregations SARA actually uses.
body_goal(V, _) :- var(V), !, fail.
body_goal((A, B), G) :- !, ( body_goal(A, G) ; body_goal(B, G) ).
body_goal((A ; B), G) :- !, ( body_goal(A, G) ; body_goal(B, G) ).
body_goal((A -> B), G) :- !, ( body_goal(A, G) ; body_goal(B, G) ).
body_goal(\+ A, G) :- !, body_goal(A, G).
body_goal(findall(_, A, _), G) :- !, body_goal(A, G).
body_goal(forall(A, B), G) :- !, ( body_goal(A, G) ; body_goal(B, G) ).
body_goal(aggregate_all(_, A, _), G) :- !, body_goal(A, G).
body_goal(true, _) :- !, fail.
body_goal(G, G) :- callable(G).

% The constants a goal pins one of its arguments to.  `purpose_(S,"domestic
% service")` says the value universe of purpose_/2 position 1 must contain that
% string, whether or not any of SARA's 376 cases ever writes it.
% An atomic body goal -- `!`, `fail` -- pins no argument; without this clause
% args/1 fails and takes the whole enclosing forall/2 with it, which silently
% drops every clause in the file after the first cut.
args(G) :- \+ compound(G), !.
args(G) :-
    key(G, K),
    compound_name_arguments(G, _, As),
    forall(nth0(I, As, A), ( ground_lit(A, V) -> assertz_new(lit(K, I, V)) ; true )).

ground_lit(A, A) :- string(A), !.
ground_lit(A, A) :- number(A), !.
ground_lit(A, A) :- atom(A), A \== [], \+ memberchk(A, ['-', '_']).
