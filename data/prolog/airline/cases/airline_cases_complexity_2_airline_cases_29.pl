/* =========  Statutory rules needed for this case  ========= */

:- use_module(library(lists)).

/* ----------------  Allowances / classes / route  ---------------- */

passenger(susan).
class(susan,premium_economy).
route(susan,europe_us).     /* Barcelona (Europe) -> Orlando (U.S.) */
flight_ticket_cost(666).

/* Carry-on allowance: 1 personal item + 1 carry-on              */
/* Only 1 of Susan's pieces meets the carry-on size limits        */

carry_on_eligible(Id) :-
    bag(Id,L,W,H,_),
    L =< 22, W =< 14, H =< 9.

/* We pick the first eligible bag as the free carry-on            */
carry_on(BagId) :-
    setof(Id, carry_on_eligible(Id), [BagId|_]).      /* first one */

/* ----------------  Baggage fees (base)  ---------------- */

base_fee(_Route,_Class,Index,0) :-          % 1st & 2nd bags free for
    Index =< 2.                             % Premium Economy
base_fee(europe_us,premium_economy,Index,200) :-
    Index  >= 3.                            % 3rd bag and higher

/* ----------------  Oversize fees  (Europe <-> US) -------------- */

oversize_fee(Sum,0)            :- Sum =< 62.
oversize_fee(Sum,30)           :- Sum  > 62, Sum =< 65.
oversize_fee(Sum,150)          :- Sum  > 65, Sum =< 115.

/* ----------------  Overweight fees (Europe <-> US) ------------- */

overweight_fee(W,0)            :- W =< 50.
overweight_fee(W,30)           :- W  > 50, W =< 53.
overweight_fee(W,100)          :- W  > 53, W =< 70.

/* If both apply, charge ONLY the higher of the two  */
extra_fee(BagId,Fee) :-
    bag(BagId,L,W,H,Weight),
    Sum is L+W+H,
    oversize_fee(Sum,OverSize),
    overweight_fee(Weight,OverWt),
    Fee is max(OverSize,OverWt).

/* ----------------  Bags data (length, width, height, weight) --- */

bag(1,19,14, 6,12).
bag(2,37,16,12,53).
bag(3,34,20,10,52).
bag(4,37,16,11,59).
bag(5,46,26,18,52).
bag(6,53,31,29,56).
bag(7,42,23,17,58).
bag(8,40,19,19,51).
bag(9,34,18,11,53).
bag(10,42,30,17,68).
bag(11,35,16,13,68).

/* ----------------  Checked-bag ordering & cost ------------------ */

checked_bag_ids(Ids) :-
    findall(Id,(bag(Id,_,_,_,_),\+carry_on(Id)),Ids).

bag_index(Id,Index) :-
    checked_bag_ids(Ids),
    nth1(Index,Ids,Id).

bag_cost(Id,Cost) :-
    passenger(P), class(P,Class), route(P,Route),
    bag_index(Id,Idx),
    base_fee(Route,Class,Idx,Base),
    extra_fee(Id,Extra),
    Cost is Base + Extra.

/* ----------------  Totals -------------------------------------- */

total_baggage_cost(Total) :-
    findall(C, (bag(Id,_,_,_,_), \+ carry_on(Id), bag_cost(Id,C)), Cs),
    sumlist(Cs,Total).

total_cost(Total) :-
    flight_ticket_cost(T),
    total_baggage_cost(Bags),
    Total is T + Bags.

/* ----------------  Query --------------------------------------- */
:- total_cost(Total), format('Total cost: ~w~n',[Total]).
:- halt.