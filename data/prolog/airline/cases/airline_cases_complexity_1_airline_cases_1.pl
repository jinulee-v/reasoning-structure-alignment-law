/* --------------  RULES FROM THE STATUTES (subset covering this case) -------------- */

/* Carry-on: Daniel uses bag #1, everything else is checked */
carry_on(1).

/* Facts for each piece (length, width, height, weight in lbs) */
bag(1,19,12, 6,11).     /* carry-on */
bag(2,40,17,15,73).
bag(3,45,21,22,84).
bag(4,44,26,23,81).
bag(5,39,21,16,83).
bag(6,40,18,16,68).
bag(7,38,22,14,63).
bag(8,37,20,18,53).

/* A bag is checked if it is not the declared carry-on */
checked_bag(Id) :- bag(Id,_,_,_,_), \+ carry_on(Id).

/* --------- size / weight derived values ---------- */
size_sum(Id,Sum)  :- bag(Id,L,W,H,_), Sum is L+W+H.
weight(Id,Wt)     :- bag(Id,_,_,_,Wt).

/* -------- oversize fees (within U.S.) ------------ */
oversize_fee(Size,200) :- Size >  65, !.
oversize_fee(Size, 30) :- Size >  62, Size =< 65, !.
oversize_fee(_,0).

/* -------- overweight fees (within U.S.) ---------- */
overweight_fee(W,200) :- W  > 70, !.
overweight_fee(W,100) :- W  > 53, W =< 70, !.
overweight_fee(W, 30) :- W  > 50, W =< 53, !.
overweight_fee(_,0).

/* The higher of the two fees applies */
extra_fee(Id,Fee) :-
    size_sum(Id,S), oversize_fee(S,F1),
    weight(Id,W),   overweight_fee(W,F2),
    (F1 >= F2 -> Fee = F1 ; Fee = F2).

/* ---------- base checked-bag fees for First Class, domestic ---------- */
/* 1st & 2nd free, 3rd = $150, 4th+ = $200 */
base_fee(Pos,0)   :- Pos < 3, !.
base_fee(3,150)   :- !.
base_fee(Pos,200) :- Pos > 3.

/* ---------- total cost for every checked bag ------------------------- */
bag_cost(Id,Cost) :-
    checked_bags_list(List),
    nth1(Pos,List,Id),
    base_fee(Pos,Base),
    extra_fee(Id,Extra),
    Cost is Base + Extra.

/* list of checked bags in id order (2 .. 8) */
checked_bags_list(List) :-
    findall(I,checked_bag(I),List).

/* sum helper */
sum_list([],0).
sum_list([H|T],S) :- sum_list(T,S1), S is H+S1.

/* --------------   OVERALL TOTAL ------------------ */
total_cost(Total) :-
    findall(C,bag_cost(_,C),BagCosts),
    sum_list(BagCosts,BagsTotal),
    Ticket = 245,
    Total is Ticket + BagsTotal.

/* ------------------- QUERY ----------------------- */
:- total_cost(Total), format('Total cost: ~w~n',[Total]).
:- halt.