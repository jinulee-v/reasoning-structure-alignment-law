/* =========================================================
   American Airlines - baggage-fee calculator
   Case:  John (Business Class)  Guangzhou  ->  Salt Lake City
   ========================================================= */

/* ----------------  Static facts for this itinerary  ---------------- */

flight_cost(1182).                                  /* ticket price */

/* carry-on limit (not used further - bag #1 is carry-on) */
carry_on_max(22,14,9).

/* Description of every item brought on the trip:
      bag(Id, Length, Width, Height, Weight).               */
bag(1,21,11, 8,11).        /* fits as carry-on - will be ignored below */

bag(2,34,18,11,52).
bag(3,36,16,13,53).
bag(4,37,18, 9,51).
bag(5,34,21, 9,52).
bag(6,39,18,11,52).
bag(7,46,24,22,59).
bag(8,44,28,24,53).
bag(9,35,18,11,63).
bag(10,43,19,20,70).
bag(11,38,18, 9,62).

/* list (constant) of all pieces that must be checked */
checked_bag_ids([2,3,4,5,6,7,8,9,10,11]).

/* --------------  Statutory rules relevant to the case  -------------- */

/* 1 + 2 checked bags are complimentary in Business Class              */

bag_fee(1,0).
bag_fee(2,0).
bag_fee(N,200) :- N>=3.                    /* 3rd and subsequent bags */

/* Sum of the three outside dimensions                                */
dims_sum(L,W,H,S) :- S is L+W+H.

/* Over-size fee - region: China <-> U.S.                                */
oversize_fee(Sum,Fee) :-
       (   Sum =< 62        -> Fee = 0
       ;   Sum =< 65        -> Fee = 30
       ;   Sum =< 115       -> Fee = 200).

/* Over-weight fee - region: China <-> U.S.
      Thresh = maximum permitted weight for the bag type              */
overweight_fee(W,Thresh,Fee) :-
       (   W =< Thresh      -> Fee = 0
       ;   W =< 53          -> Fee = 30
       ;   W =< 70          -> Fee = 100
       ;   W =< 100         -> Fee = 450).

/* Penalty applied to a bag = higher of over-size vs over-weight       */
penalty(BagId,complimentary,Pen) :-        /* complimentary bag -> 70-lb limit */
       bag(BagId,L,W,H,Weight),
       dims_sum(L,W,H,Sum),
       oversize_fee(Sum,OS),
       overweight_fee(Weight,70,OW),
       Pen is max(OS,OW).

penalty(BagId,charged,Pen) :-              /* charged bag -> 50-lb limit */
       bag(BagId,L,W,H,Weight),
       dims_sum(L,W,H,Sum),
       oversize_fee(Sum,OS),
       overweight_fee(Weight,50,OW),
       Pen is max(OS,OW).

/* -------------------  Helper predicates  --------------------------- */

/* pick 2 different bag Ids (F1 < F2) from a list */
choose_two(List,F1,F2) :-
       append(_,[F1|Tail],List),
       member(F2,Tail).

/* place the 2 complimentary bags in the first 2 positions;
   the remaining bags keep their original relative order              */
ordered_list(F1,F2,Ordered) :-
       checked_bag_ids(All),
       select(F1,All,Rest1),
       select(F2,Rest1,Rest),
       Ordered = [F1,F2|Rest].

/* compute cost for ONE particular allocation of the 2 freebies       */
cost_for_choice(F1,F2,Total) :-
       ordered_list(F1,F2,Ordered),
       cost_bags(Ordered,1,BagFees,Penalties),
       flight_cost(Tix),
       Total is Tix + BagFees + Penalties.

/* walk through the ordered list, accumulating bag fees & penalties   */
cost_bags([],_,0,0).
cost_bags([Bag|Bs],Idx,SumFee,SumPen) :-
       (Idx =< 2 -> Type = complimentary ; Type = charged),
       bag_fee(Idx,Base),
       penalty(Bag,Type,Pen),
       Next is Idx+1,
       cost_bags(Bs,Next,RestFee,RestPen),
       SumFee is Base + RestFee,
       SumPen is Pen + RestPen.

/* minimal total cost over all ways of selecting the 2 free bags      */
compute_total(Min) :-
       checked_bag_ids(L),
       findall(T, (choose_two(L,F1,F2), cost_for_choice(F1,F2,T)), Ts),
       min_list(Ts,Min).

/* -------------------------  Query  -------------------------------- */
:- compute_total(Cost), format('Total cost: ~w~n', [Cost]), halt.