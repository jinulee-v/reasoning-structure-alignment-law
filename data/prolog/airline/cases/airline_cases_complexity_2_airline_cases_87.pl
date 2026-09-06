:- format("~w~n", ["Label: 5388"]).
/* =========================================================
   Case:  Thomas - First Class   (Guangzhou  -  San Francisco)
   Goal:  compute total trip cost (ticket + bags)
   Statutory bases: American Airlines published bag rules
   ========================================================= */

/* ------------  Ticket cost  ------------------------------ */
flight_cost(1418).

/* ------------  Bags (carry-on is #1, not repeated here) -- */
/* bag(Id,Length,Width,Height,Weight) - checked pieces only  */
bag(2,36,15,14,62).
bag(3,48,25,25,51).
bag(4,35,17,13,53).
bag(5,37,17, 9,84).
bag(6,46,28,20,97).
bag(7,33,19,11,77).
bag(8,37,15,13,52).
bag(9,34,18,12,64).
bag(10,35,20,10,80).
bag(11,39,14,13,80).

/* constant list of the checked-bag Ids                       */
checked_bag_ids([2,3,4,5,6,7,8,9,10,11]).

/* ------------  Dimension helpers  ------------------------ */
dims_sum(L,W,H,S) :- S is L+W+H.

/* ------------  Oversize fees - China <-> U.S. --------------- */
/*   0-62 in  -> $0     */
/*  62-65 in  -> $30    */
/*  65-115 in -> $200   */
oversize_fee(S,Fee) :-
    (  S =< 62  -> Fee = 0
    ;  S =< 65  -> Fee = 30
    ;               Fee = 200).

/* ------------  Overweight fees - China <-> U.S. ------------- */
/* Threshold is 70 lb for complimentary pieces, 50 lb if charged */
overweight_fee(W,Threshold,Fee) :-
    (  W =< Threshold -> Fee = 0
    ;  W =< 53        -> Fee = 30
    ;  W =< 70        -> Fee = 100
    ;  W =< 100       -> Fee = 450 ).

/* ------------  Penalty for a single bag ------------------- */
/* "The higher fee between oversize and overweight applies." */
penalty(BagId,complimentary,Pen) :-
       bag(BagId,L,W,H,Weight),
       dims_sum(L,W,H,Sum),
       oversize_fee(Sum,OS),
       overweight_fee(Weight,70,OW),      % 70-lb limit for free bags
       Pen is max(OS,OW).

penalty(BagId,charged,Pen) :-
       bag(BagId,L,W,H,Weight),
       dims_sum(L,W,H,Sum),
       oversize_fee(Sum,OS),
       overweight_fee(Weight,50,OW),      % 50-lb limit when a bag fee applies
       Pen is max(OS,OW).

/* ------------  First-Class bag fees on this route --------- */
/* 1st-3rd pieces $0 ; 4th+ $200                              */
bag_fee(N,0)   :- N>=1, N=<3.
bag_fee(N,200) :- N>=4.

/* ------------  Choose 3 complimentary bags ----------------*/
choose_three(List,A,B,C) :-
       append(_, [A|T1], List),
       append(_, [B|T2], T1),
       member(C, T2),
       A @< B, B @< C.      % enforce ascending order (no duplicates)

/* place freebies first, keep original order of the rest      */
ordered_list(A,B,C,Ordered) :-
       checked_bag_ids(All),
       select(A,All,R1),
       select(B,R1,R2),
       select(C,R2,Rest),
       Ordered = [A,B,C|Rest].

/* ------------  Cost for one particular triple ------------- */
cost_for_choice(A,B,C,Total) :-
       ordered_list(A,B,C,Ord),
       cost_bags(Ord,1,CostBags,Penalties),
       flight_cost(Tix),
       Total is Tix + CostBags + Penalties.

/* walk the ordered list, accumulating fees and penalties     */
cost_bags([],_,0,0).
cost_bags([Bag|Bs],Idx,CostSum,PenSum) :-
       (Idx =< 3 -> Type = complimentary ; Type = charged),
       bag_fee(Idx,BF),
       penalty(Bag,Type,Pen),
       Next is Idx+1,
       cost_bags(Bs,Next,CostRest,PenRest),
       CostSum is BF + CostRest,
       PenSum  is Pen + PenRest.

/* ------------  Global minimum over all triples -------------*/
total_cost(Min) :-
       checked_bag_ids(L),
       findall(T,
               ( choose_three(L,A,B,C),
                 cost_for_choice(A,B,C,T)),
               Totals),
       min_list(Totals,Min).

/* ------------  Run query & print ---------------------------*/
:- total_cost(Total), format('Total cost: ~w~n', [Total]).
:- halt.