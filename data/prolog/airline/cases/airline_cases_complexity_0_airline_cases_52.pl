:- format("~w~n", ["Label: 751"]).
/* ====================================================================
   William - Business Class - New Orleans  ->  New York   (domestic)
   ==================================================================== */

/* ---------------  Ticket price  ------------------------------------ */
flight_cost(281).


/* ---------------  Checked bags (carry-on bag is not listed) -------- */
/*    bag(Id, Length, Width, Height, Weight)                          */
bag(2,33,18,12,65).
bag(3,33,19,11,52).
bag(4,34,20,11,52).
bag(5,33,16,14,66).


/* ---------------  Ordered universe of checked-bag IDs -------------- */
checked_bag_ids([2,3,4,5]).

/* ---------------  Statutory rules for this itinerary --------------- */

/* (1) Sum of dimensions */
dims_sum(L,W,H,S) :- S is L+W+H.

/* (2) Oversize fee - within / between U.S. and Canada */
oversize_fee(Sum,Fee) :-
       (   Sum =< 62      -> Fee = 0
       ;   Sum =< 65      -> Fee = 30
       ;   Sum =< 115     -> Fee = 200 ).

/* (3) Overweight fee - within / between U.S. and Canada             */
/*     Threshold is 70 lbs for the 1st-2nd complimentary bags,       */
/*     and 50 lbs for every subsequently CHARGED bag                 */
overweight_fee(W,Threshold,Fee) :-
       (   W =< Threshold  -> Fee = 0
       ;   W =< 53         -> Fee = 30
       ;   W =< 70         -> Fee = 100
       ;   W =< 100        -> Fee = 200 ).

/* (4) Penalty for a bag = higher of oversize vs. overweight fee      */
penalty(BagId,complimentary,Pen) :-
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

/* (5) Base checked-bag fee for Business Class on this route         */
bag_fee(1,0).              /* 1st bag (complimentary)  */
bag_fee(2,0).              /* 2nd bag (complimentary)  */
bag_fee(3,150).            /* 3rd bag                  */
bag_fee(N,200) :- N>=4.    /* 4th bag and beyond       */

/* ---------------  Helper predicates  ------------------------------ */

/* Choose 2 different elements F1<F2 from a list */
choose_two(List,F1,F2) :-
       append(_,[F1|Tail],List),
       member(F2,Tail).

/* Remove the chosen freebies & build the final ordered list          */
/* - freebies occupy positions 1 and 2                                */
ordered_list(F1,F2,Ordered) :-
       checked_bag_ids(All),
       select(F1,All,Rest1),
       select(F2,Rest1,Rest),
       Ordered = [F1,F2|Rest].

/* Cost for one specific choice of the 2 complimentary bags */
cost_for_choice(F1,F2,Total) :-
       ordered_list(F1,F2,Ordered),
       cost_bags(Ordered,1,BagCost,Penalties),
       flight_cost(Flight),
       Total is Flight + BagCost + Penalties.

/* Walk through the ordered list accumulating base fees & penalties */
cost_bags([],_,0,0).
cost_bags([Bag|Bs],Idx,CostSum,PenSum) :-
       (Idx =< 2 -> Type = complimentary ; Type = charged),
       bag_fee(Idx,Fee),
       penalty(Bag,Type,Pen),
       NextIdx is Idx+1,
       cost_bags(Bs,NextIdx,CostRest,PenRest),
       CostSum is Fee + CostRest,
       PenSum  is Pen + PenRest.

/* ---------------  Grand-total minimisation ------------------------ */
total_cost(MinTotal) :-
       checked_bag_ids(L),
       findall(T,(choose_two(L,F1,F2), cost_for_choice(F1,F2,T)),Totals),
       min_list(Totals,MinTotal).


/* ---------------  Query & output ---------------------------------- */
:- total_cost(Total), format('Total cost: ~w~n', [Total]).
:- halt.