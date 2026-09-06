% Emit every clause of every reference program in a canonical form, so that
% "the same rule written twice" can be recognised across files.
%
%   swipl dump_clauses.pl -- <cases dir> > clauses.tsv
%
% Each line:  <file> \t <Name>/<Arity> \t <canonical clause text>
%
% DeonticBench ships no single statute file, but it does ship the statute's
% rules --- once per case, abridged to that case and mixed in with its facts.
% This is the first half of recovering them: variables are numbered and layout
% is flattened, so that two files that wrote the same rule differently are
% recognisable as the same rule.  `check_shipped_rules.py` is the second half,
% which compares them by what they *compute* rather than by how they are
% spelled.
:- initialization(main, main).

main([Dir]) :-
    directory_files(Dir, Fs), sort(Fs, Sorted),
    forall((member(F, Sorted), file_name_extension(Base, pl, F)),
           ( atomic_list_concat([Dir,'/',F], P), dump(Base, P) )).

dump(Base, P) :-
    catch(( open(P, read, S),
            repeat,
            catch(read_term(S, T, []), _, T = end_of_file),
            ( T == end_of_file -> !, close(S)
            ; emit(Base, T), fail )), _, true).

emit(_, (:- _)) :- !.
emit(Base, T) :-
    ( T = (H :- _) -> true ; H = T ),
    functor(H, N, A),
    copy_term(T, T2), numbervars(T2, 0, _),
    with_output_to(string(Str), print_canonical_line(T2)),
    format("~w\t~w/~w\t~w~n", [Base, N, A, Str]).

print_canonical_line(T) :-
    with_output_to(string(S0), portray_clause(T)),
    split_string(S0, "\n", " \t", Parts),
    exclude(==(""), Parts, Ps),
    atomic_list_concat(Ps, ' ', Joined),
    write(Joined).
