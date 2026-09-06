/* -------------------------------------------------
   Facts describing Michael's itinerary and bags
   ------------------------------------------------- */

/* price of the airline ticket */
flight_cost(294).

/* each checked bag: bag(Id,Length,Width,Height,Weight) */
bag(2, 34,22, 9, 56).
bag(3, 35,19,11, 53).
bag(4, 43,20,19, 64).
bag(5, 35,17,12, 51).
bag(6, 40,24,14, 73).
bag(7, 49,32,29, 51).
bag(8, 46,23,19, 69).
bag(9, 49,32,28, 99).
bag(10,33,17,14, 51).
bag(11,46,26,22, 61).

/* list of all checked-bag Ids (carry-on #1 is excluded) */
checked_bag_ids([2,3,4,5,6,7,8,9,10,11]).

/* -------------------------------------------------
   Statutory rules for this 'within-U.S.' Business-class trip
   ------------------------------------------------- */

/* dimensional sum of a bag */
dims_sum(L,W,H,S) :- S is L+W+H.

/* oversize fees - within / between U.S. and Canada */
oversize_fee(Sum,Fee) :-
       ( Sum =< 62  -> Fee = 0
       ; Sum =< 65  -> Fee = 30
       ; Sum =< 115 -> Fee = 200 ).

/* overweight fees
     Thresh = 70 lbs for complimentary bags
     Thresh = 50 lbs for charged bags                */
overweight_fee(W,Thresh,Fee) :-
       ( W =< Thresh -> Fee = 0
       ; W =< 53     -> Fee = 30
       ; W =< 70     -> Fee = 100
       ; W =< 100    -> Fee = 200 ).

/* penalty = higher of oversize vs. overweight fee */
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

/* checked-bag base fee schedule - Business Class, domestic */
bag_fee(1,0).
bag_fee(2,0).
bag_fee(3,150).
bag_fee(N,200) :- N >= 4.

/* -------------------------------------------------
   Helper predicates
   ------------------------------------------------- */

/* choose two different items (free checked-bag allowance) */
choose_two(List,X,Y) :-
       append(_, [X|Tail], List),
       member(Y, Tail).

/* move the 2 freebies to positions 1-2, keep order of the rest */
ordered_list(F1,F2,Ordered) :-
       checked_bag_ids(All),
       select(F1,All,R1),
       select(F2,R1,R),
       Ordered = [F1,F2|R].

/* compute cost for a particular selection of the 2 free bags */
cost_for_choice(F1,F2,Total) :-
       ordered_list(F1,F2,Ord),
       cost_bags(Ord,1,Base,Pen),
       flight_cost(Tix),
       Total is Tix + Base + Pen.

/* walk through the ordered bags accumulating fees */
cost_bags([],_,0,0).
cost_bags([Bag|Bs],Idx,BaseTot,PenTot) :-
       (Idx =< 2 -> Type = comp ; Type = charged),
       bag_fee(Idx,BFee),
       penalty(Bag,Type,Pen),
       NextIdx is Idx + 1,
       cost_bags(Bs,NextIdx,BaseRest,PenRest),
       BaseTot is BFee + BaseRest,
       PenTot  is Pen  + PenRest.

/* find the minimum total over every possible choice of freebies */
compute_total(Min) :-
       checked_bag_ids(L),
       findall(T, (choose_two(L,A,B), cost_for_choice(A,B,T)), Ts),
       min_list(Ts, Min).

/* -------------------------------------------------
   Query & output
   ------------------------------------------------- */
:- compute_total(Cost), format('Total cost: ~w~n', [Cost]), halt.