/* --------------------------------------------------------- */
/*  Facts describing Karen's itinerary and her belongings    */
/* --------------------------------------------------------- */

/* ticket price */
flight_cost(265).

/* bag(Id,Length,Width,Height,Weight) */
bag(1,21,11, 8,  6).    /* carry-on - not checked */
bag(2,34,17,14, 64).
bag(3,33,21,11, 60).
bag(4,34,16,13, 53).
bag(5,54,31,26, 69).
bag(6,46,22,21, 58).
bag(7,43,21,17, 56).
bag(8,45,25,20, 54).
bag(9,33,20,11, 52).
bag(10,34,16,14,53).
bag(11,47,29,22,67).

/* list of all checked bags (carry-on #1 excluded) */
checked_bag_ids([2,3,4,5,6,7,8,9,10,11]).

/* --------------------------------------------------------- */
/*  Statutory charges for Europe  <->  United States routes    */
/* --------------------------------------------------------- */

/* oversize fees (sum = L+W+H, inches) */
oversize_fee(Sum,Fee) :-
      (   Sum =< 62  -> Fee = 0
      ;   Sum =< 65  -> Fee = 30
      ;   Sum =< 115 -> Fee = 150 ).

/* overweight fees - two different weight limits:
      - complimentary bag -> 70-lb threshold
      - charged bag       -> 50-lb threshold               */
overweight_fee(W,Thresh,Fee) :-
      (   W =< Thresh -> Fee = 0
      ;   W =< 53     -> Fee = 30
      ;   W =< 70     -> Fee = 100
      ;   W =< 100    -> Fee = 200 ).

/* First-Class base fee by ordinal position (Europe-U.S.) */
bag_fee(1,0).
bag_fee(2,0).
bag_fee(3,0).
bag_fee(N,200) :- N >= 4.

/* --------------------------------------------------------- */
/*  Auxiliary predicates                                     */
/* --------------------------------------------------------- */

dims_sum(L,W,H,S) :- S is L+W+H.

/* penalty is the higher of the oversize vs overweight fee */
penalty(BagId,comp,Pen) :-
      bag(BagId,L,W,H,Weight),
      dims_sum(L,W,H,Sum),
      oversize_fee(Sum,OS),
      overweight_fee(Weight,70,OW),     % 70-lb allowance for freebies
      Pen is max(OS,OW).

penalty(BagId,charged,Pen) :-
      bag(BagId,L,W,H,Weight),
      dims_sum(L,W,H,Sum),
      oversize_fee(Sum,OS),
      overweight_fee(Weight,50,OW),     % 50-lb allowance for paid bags
      Pen is max(OS,OW).

/* choose three different elements (A < B < C) from a list */
choose_three(List,A,B,C) :-
      append(_,[A|T1],List),
      append(_,[B|T2],T1),
      member(C,T2).

/* put the 3 complimentary pieces first in the ordered list */
ordered_list_three(A,B,C,Ordered) :-
      checked_bag_ids(All),
      select(A,All,R1),
      select(B,R1,R2),
      select(C,R2,Rest),
      Ordered = [A,B,C|Rest].

/* walk the ordered list, accumulating base fees & penalties */
cost_bags([],_,0,0).
cost_bags([Bag|Bs],Idx,CostSum,PenSum) :-
      (Idx =< 3 -> Kind = comp ; Kind = charged),
      bag_fee(Idx,F),
      penalty(Bag,Kind,P),
      Next is Idx+1,
      cost_bags(Bs,Next,Crest,Prest),
      CostSum is F + Crest,
      PenSum  is P + Prest.

/* compute cost for one particular choice of the 3 free bags */
cost_for_choice(A,B,C,Total) :-
      ordered_list_three(A,B,C,Ordered),
      cost_bags(Ordered,1,BaseFees,Penalties),
      flight_cost(Flight),
      Total is Flight + BaseFees + Penalties.

/* overall minimum cost across all ways to pick the 3 freebies */
compute_total(MinTotal) :-
      checked_bag_ids(L),
      findall(T,
              ( choose_three(L,A,B,C),
                cost_for_choice(A,B,C,T) ),
              Totals),
      min_list(Totals,MinTotal).

/* --------------------------------------------------------- */
/*  Query & display                                          */
/* --------------------------------------------------------- */
:- compute_total(Cost), format('Total cost: ~w~n', [Cost]), halt.