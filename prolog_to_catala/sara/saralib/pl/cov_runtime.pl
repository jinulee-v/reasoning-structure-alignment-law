% Coverage and trace runtime for the instrumented statutes.
%
% Every goal position in the statutes is wrapped by prolog_to_catala/sara/saralib/pl/
% cover_transform.pl so that it calls cov/1 twice: once with a `:c` point when
% the goal is called, once with a `:f` point when the call has no solution.  A
% clause that runs to the end of its body records a `:e` point.  This file is
% everything those calls land in.
%
% Two consumers, one mechanism:
%
%   * the *set* of points reached, which is branch coverage and drives
%     generation -- a world is worth keeping when it reaches a point, or a
%     combination of points, no earlier world reached;
%   * the *sequence* of points reached, which is the execution trace and is
%     what a discrepancy report shows a reader.
%
% The sequence is off unless a trace stream is open, so the cost on a coverage
% run is one indexed lookup of a predicate with no clauses.

:- dynamic covd/1.              % points reached since the last reset
:- dynamic covu/1.              % points reached at any time in this process
:- dynamic cov_stream/1.        % the open trace stream, if tracing

cov(P) :-
    (   cov_stream(S)
    ->  format(S, "~w~n", [P])
    ;   true
    ),
    (   covd(P) -> true ; assertz(covd(P)) ).

%!  cov_trace_to(+File) is det.
%
%   Start recording the ordered sequence of points to File.  Called by the
%   harness when SARA_TRACE names a path; a test case run for its verdict
%   alone never opens one.
cov_trace_to(File) :-
    end_cov_trace,
    open(File, write, S),
    assertz(cov_stream(S)).

end_cov_trace :-
    (   retract(cov_stream(S)) -> close(S) ; true ).

%!  reset_cov is det.
%
%   Start a fresh per-world set, folding what was reached into the running
%   union first.  The bounded-exhaustive enumerator runs thousands of worlds
%   inside one process and needs both: each world's own path, and what the
%   whole enumeration covered.
reset_cov :-
    forall(covd(P), ( covu(P) -> true ; assertz(covu(P)) )),
    retractall(covd(_)).

%!  cov_signature(-Hash) is det.
%
%   A stable fingerprint of the branches taken since the last reset.  Two
%   worlds with the same signature drove the statutes down the same path, so
%   only one of them has to be put to the Catala side -- which is what makes
%   "every distinct execution path was checked" affordable to claim.
cov_signature(Hash) :-
    findall(P, covd(P), Ps0), sort(Ps0, Ps), variant_sha1(Ps, Hash).

dump_cov(File) :-
    findall(P, ( covd(P) ; covu(P) ), Ps0), sort(Ps0, Ps),
    setup_call_cleanup(open(File, write, S),
        forall(member(P, Ps), format(S, "~w~n", [P])),
        close(S)).
