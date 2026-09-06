% Run many airline worlds in one SWI process, reporting each world's verdict
% and the branch-point signature of the path it drove the oracle down.
%
%   swipl airline_enum.pl -- <covered_oracle.pl> <worlds.pl> <out.txt>
%
% `worlds.pl` holds terms
%     world(Id, Origin, Destination, Cabin, Ticket, [item(I,K,L,W,H,Wt)|...],
%           StatusTicketing, StatusCheckin, Cardmember, Military, Flagship,
%           Children).
% The last six are the Complimentary Bags attributes; `Cardmember` and
% `Flagship` are the atoms yes/no.
% and each line of `out.txt` is
%     Id <TAB> Total <TAB> Accepted <TAB> Signature
% or, when the world raises,
%     Id <TAB> error <TAB> error <TAB> Signature
%
% Selection consults Prolog alone.  Two worlds with the same signature drove
% the statute down the same path and cannot tell the two systems apart, so only
% one of them ever becomes a test case --- the criterion `prolog_to_catala/sara` settled
% on, carried over unchanged.

:- initialization(main, main).

:- dynamic origin/1, destination/1, cabin/1, ticket/1, item/6,
           status_at_ticketing/1, status_at_checkin/1, cardmember/0,
           military/1, flagship/0, children/1.

main([Oracle, Worlds, Out]) :-
    ensure_loaded(Oracle),
    consult(Worlds),
    setup_call_cleanup(
        open(Out, write, S),
        forall(world(Id, O, D, C, T, Items, ST, SC, Card, Mil, Flag, Kids),
               one(S, Id, O, D, C, T, Items, ST, SC, Card, Mil, Flag, Kids)),
        close(S)),
    % the union of every point any world in this batch reached, which is the
    % coverage number the report quotes
    atom_concat(Out, '.cov', CovFile),
    reset_cov,
    dump_cov(CovFile).

one(S, Id, O, D, C, T, Items, ST, SC, Card, Mil, Flag, Kids) :-
    retractall(origin(_)), retractall(destination(_)),
    retractall(cabin(_)), retractall(ticket(_)), retractall(item(_,_,_,_,_,_)),
    retractall(status_at_ticketing(_)), retractall(status_at_checkin(_)),
    retractall(cardmember), retractall(military(_)),
    retractall(flagship), retractall(children(_)),
    assertz(origin(O)), assertz(destination(D)),
    assertz(cabin(C)), assertz(ticket(T)),
    forall(member(item(I,K,L,W,H,Wt), Items), assertz(item(I,K,L,W,H,Wt))),
    assertz(status_at_ticketing(ST)), assertz(status_at_checkin(SC)),
    assertz(military(Mil)), assertz(children(Kids)),
    ( Card == yes -> assertz(cardmember) ; true ),
    ( Flag == yes -> assertz(flagship) ; true ),
    reset_cov,
    (   catch(( total_cost(Total), ( accepted -> Acc = true ; Acc = false ) ),
              _, fail)
    ->  true
    ;   Total = error, Acc = error ),
    cov_signature(Sig),
    format(S, "~w\t~w\t~w\t~w~n", [Id, Total, Acc, Sig]).
