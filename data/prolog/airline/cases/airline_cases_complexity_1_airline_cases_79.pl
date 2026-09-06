/* =========================================================
   Statutory computation for Elizabeth - Dallas -> Sydney
   Main Cabin - issued 2024 rules
   ========================================================= */

/* ----------------  Trip facts  --------------------------- */

flight_cost(675).

/* checked pieces only  (bag(Id,Length,Width,Height,Weight)) */
bag(2,40,22,16,64).
bag(3,33,18,13,51).
bag(4,46,28,22,63).
bag(5,34,22, 9,52).
bag(6,34,18,13,69).
bag(7,47,23,23,53).
bag(8,34,23,11,51).

/* list of all checked-bag Ids */
checked_bag_ids([2,3,4,5,6,7,8]).

/* ----------------  Statutory rules  ---------------------- */

/* dimension sum */
dims_sum(L,W,H,S) :- S is L+W+H.

/* oversize fees - to / from Australia / New Zealand */
oversize_fee(Sum,Fee) :-
       (   Sum =< 62      -> Fee = 0
       ;   Sum =< 65      -> Fee = 30
       ;   Sum =< 115     -> Fee = 200 ).

/* overweight fees
   - complimentary bag: 70-lb limit
   - charged bag      : 50-lb limit                                  */
overweight_fee(W,Thresh,Fee) :-
       (   W =< Thresh    -> Fee = 0
       ;   W =< 53        -> Fee = 30
       ;   W =< 70        -> Fee = 100
       ;   W =< 100       -> Fee = 200 ).

/* penalty = higher of oversize vs overweight                      */
penalty(BagId,comp,Pen) :-
       bag(BagId,L,W,H,Weight),
       dims_sum(L,W,H,Sum),
       oversize_fee(Sum,OS),
       overweight_fee(Weight,70,OW),
       Pen is max(OS,OW).

penalty(BagId,charged,Pen) :-
       bag(BagId,L,W,H,Weight),
       dims_sum(L,W,H,Sum),
       oversize_fee(Sum,OS),
       overweight_fee(Weight,50,OW),
       Pen is max(OS,OW).

/* Main Cabin bag fees - U.S. <-> Australia                           */
bag_fee(1,0).
bag_fee(2,100).
bag_fee(N,200) :- N >= 3.

/* ----------------  Helper predicates  -------------------- */

/* choose a complimentary (1st-bag) candidate */
choose_one(List,Bag) :- member(Bag,List).

/* put that bag first, keep the rest in original order */
ordered_list(First,Ordered) :-
       checked_bag_ids(All),
       select(First,All,Rest),
       Ordered = [First|Rest].

/* cost for a particular placement of the complimentary bag */
cost_for_choice(FreeBag,Total) :-
       ordered_list(FreeBag,Ordered),
       cost_bags(Ordered,1,FeeSum,PenSum),
       flight_cost(Flight),
       Total is Flight + FeeSum + PenSum.

/* walk the list, adding base fees and penalties */
cost_bags([],_,0,0).
cost_bags([Bag|Bs],Idx,FeeTot,PenTot) :-
       (Idx =:= 1 -> Type = comp ; Type = charged),
       bag_fee(Idx,Fee),
       penalty(Bag,Type,Pen),
       NextIdx is Idx + 1,
       cost_bags(Bs,NextIdx,FeeRest,PenRest),
       FeeTot is Fee + FeeRest,
       PenTot is Pen + PenRest.

/* minimal total over all ways of picking the free bag */
total_cost(Min) :-
       checked_bag_ids(L),
       findall(T,(choose_one(L,B),cost_for_choice(B,T)),Totals),
       min_list(Totals,Min).

/* ----------------  Query & output  ----------------------- */
:- total_cost(Total), format('Total cost: ~w~n', [Total]).
:- halt.