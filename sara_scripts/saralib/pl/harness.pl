% main/0 for a generated test case, copied to sara_port/build/harness.pl.
%
% A generated `prolog.pl` is the whole input: the statutes, the world model as
% facts, and one `sara_goal/1` naming the query.  It ends by loading this file,
% so the case runs as
%
%     swipl -q -f prolog.pl -g main -t halt
%
% from any directory, and prints exactly one line:
%
%     VERDICT true | false | error
%
% Two optional environment variables, both set by run_test_cases.py and neither
% needed to reproduce a verdict by hand:
%
%     SARA_COV    write the set of branch points reached to this file
%     SARA_TRACE  write the ordered sequence of them to this file
%     SARA_LIMIT  seconds before the query is abandoned (default 120)

:- use_module(library(time)).

main :-
    ( getenv('SARA_TRACE', T) -> cov_trace_to(T) ; true ),
    ( getenv('SARA_LIMIT', LS), atom_number(LS, L) -> true ; L = 120 ),
    sara_goal(G),
    catch(
      call_with_time_limit(L, ( G -> R = true ; R = false )),
      E,
      ( R = error, print_message(error, E) )),
    end_cov_trace,
    format("VERDICT ~w~n", [R]),
    ( getenv('SARA_COV', C) -> dump_cov(C) ; true ).
