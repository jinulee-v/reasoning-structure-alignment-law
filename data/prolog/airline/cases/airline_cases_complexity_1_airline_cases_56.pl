/* =========================================================
   Jessica - Sydney (Australia)  ->  Seattle (U.S.A.)
   Main Cabin

   Goal:  Compute the minimum total trip cost (ticket +
          all checked-bag base fees + oversize / overweight
          penalties), applying American Airlines' published
          bag-fee rules for travel to / from Australia.
   ========================================================= */


/* ------------  BASIC FACTS  -------------------------------- */

flight_cost(485).                  /* price of passenger ticket  */
cabin(main_cabin).

/*     bag(Id, Length, Width, Height, Weight)                   */
bag(1,20,11, 6,  7).      /* carry-on backpack                 */
bag(2,54,30,30, 63).
bag(3,33,20,10, 61).
bag(4,44,23,20, 59).
bag(5,35,15,14, 66).
bag(6,48,30,23, 53).
bag(7,37,13,14, 52).
bag(8,36,13,14, 53).


/* ------------  CARRY-ON LIMITS  ----------------------------- */

carry_on_max(22,14,9).

carry_on(Id) :-
       bag(Id,L,W,H,_),
       carry_on_max(MaxL,MaxW,MaxH),
       L =< MaxL, W =< MaxW, H =< MaxH.


/* ------------  CHECKED-BAG LIST  ---------------------------- */

checked_bag_ids(Ids) :-
       findall(Id,(bag(Id,_,_,_,_), \+ carry_on(Id)), Ids).



/* ------------  SIZE  /  WEIGHT HELPERS  -------------------- */

dims_sum(L,W,H,S) :- S is L+W+H.



/* ------------  OVERSIZE FEES  (Australia <-> U.S.)  -------- */

oversize_fee(Sum,Fee) :-
       (  Sum =< 62           -> Fee = 0
       ;  Sum =< 65           -> Fee = 30
       ;  Sum =< 115          -> Fee = 200).



/* ------------  OVERWEIGHT FEES  (Australia <-> U.S.)  ------- */
/* Thresh = allowed weight (70 lb for complimentary, 50 lb charged) */

overweight_fee(W,Thresh,Fee) :-
       (  W =< Thresh         -> Fee = 0
       ;  W =< 53             -> Fee = 30
       ;  W =< 70             -> Fee = 100
       ;  W =< 100            -> Fee = 200 ).     % (>70 not accepted; never reached here)



/* ------------  PENALTY (oversize / overweight)  ------------- */

penalty(BagId,comp,Pen) :-        /* complimentary bag -> 70-lb limit */
       bag(BagId,L,W,H,Weight),
       dims_sum(L,W,H,Sum),
       oversize_fee(Sum,OS),
       overweight_fee(Weight,70,OW),
       Pen is max(OS,OW).

penalty(BagId,charged,Pen) :-     /* charged bag -> 50-lb limit       */
       bag(BagId,L,W,H,Weight),
       dims_sum(L,W,H,Sum),
       oversize_fee(Sum,OS),
       overweight_fee(Weight,50,OW),
       Pen is max(OS,OW).



/* ------------  BASE CHECKED-BAG FEES  (Main Cabin) ---------- */
/*   to / from Australia / New Zealand                          */

bag_fee(1,0).          /* 1st checked bag complimentary       */
bag_fee(2,100).        /* 2nd                                */
bag_fee(N,200) :- N>=3.



/* ------------  CHOOSING THE COMPLIMENTARY BAG  -------------- */

choose_free(Free,Rest) :-
       checked_bag_ids(All),
       select(Free,All,Rest).

ordered_list(Free,Ordered) :-
       choose_free(Free,Rest),
       Ordered = [Free|Rest].      /* free bag is placed first */



/* ------------  COST FOR A PARTICULAR ORDERING  -------------- */

cost_for_order(List,Total) :-
       cost_bags(List,1,BaseFees,Penalties),
       flight_cost(F),
       Total is F + BaseFees + Penalties.

cost_bags([],_,0,0).
cost_bags([Bag|Bs],Idx,BaseSum,PenSum) :-
       (Idx =:= 1 -> Type = comp ; Type = charged),
       bag_fee(Idx,BFee),
       penalty(Bag,Type,Pen),
       Next is Idx+1,
       cost_bags(Bs,Next,BaseRest,PenRest),
       BaseSum is BFee + BaseRest,
       PenSum  is Pen  + PenRest.



/* ------------  MINIMUM TOTAL COST  -------------------------- */

compute_total(MinCost) :-
       setof(Cost,
             Free^List^(ordered_list(Free,List), cost_for_order(List,Cost)),
             Costs),
       min_list(Costs,MinCost).



/* ------------  QUERY & OUTPUT  ------------------------------ */
:- compute_total(Cost), format('Total cost: ~w~n', [Cost]), halt.