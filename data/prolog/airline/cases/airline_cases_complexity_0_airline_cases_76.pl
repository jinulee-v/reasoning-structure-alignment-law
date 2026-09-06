:- format("~w~n", ["Label: 1019"]).
/* ============================================================
   Statutory rules and facts for Jessica's trip
   ============================================================ */

/* ---------- ticket price ----------------------------------- */
flight_cost(209).


/* ---------- list of checked bags: bag(Id,Length,Width,Height,Weight) */
bag(2,39,19,14,51).
bag(3,35,16,13,61).
bag(4,46,27,23,84).
bag(5,37,14,12,70).

/* list (constant) of all checked-bag Ids */
checked_bag_ids([2,3,4,5]).



/* ============================================================
   Statutory rules (Within / between U.S. and Canada route)
   ============================================================ */

/* ----- dimensional sum ------------------------------------- */
dims_sum(L,W,H,S) :- S is L+W+H.


/* ----- oversize fee  (Within / between U.S. and Canada) ----- */
oversize_fee(Sum,Fee) :-
       (   Sum =< 62      -> Fee = 0
       ;   Sum =< 65      -> Fee = 30
       ;   Sum =< 115     -> Fee = 200 ).


/* ----- overweight fee  (Within / between U.S. and Canada) --- */
/* Threshold is 70 lbs for COMPLIMENTARY (Business cabin, 1st-2nd bags)
   Threshold is 50 lbs for CHARGED bags (3rd, 4th ...)             */
overweight_fee(W,Thresh,Fee) :-
       (   W =< Thresh        -> Fee = 0
       ;   W =< 53            -> Fee = 30
       ;   W =< 70            -> Fee = 100
       ;   W =< 100           -> Fee = 200 ).


/* ----- penalty: higher of oversize vs overweight ------------ */
penalty(BagId,comp,Pen) :-
       bag(BagId,L,W,H,Weight),
       dims_sum(L,W,H,Sum),
       oversize_fee(Sum,OS),
       overweight_fee(Weight,70,OW),          % complimentary => 70-lb limit
       Pen is max(OS,OW).

penalty(BagId,charged,Pen) :-
       bag(BagId,L,W,H,Weight),
       dims_sum(L,W,H,Sum),
       oversize_fee(Sum,OS),
       overweight_fee(Weight,50,OW),          % charged bag => 50-lb limit
       Pen is max(OS,OW).


/* ----- checked-bag base fee for Business class on this route */
bag_fee(1,0).
bag_fee(2,0).
bag_fee(3,150).
bag_fee(4,200).
bag_fee(N,200) :- N>=5.



/* ============================================================
   Helper predicates for searching cheapest combination
   ============================================================ */

/* choose 2 different elements (F1<F2) from a list */
choose_two(List,F1,F2) :-
       append(_,[F1|Tail],List),
       member(F2,Tail).


/* order the master list putting the two complimentary first */
ordered_list(F1,F2,Ordered) :-
       checked_bag_ids(All),
       select(F1,All,Rest1),
       select(F2,Rest1,Rest),
       Ordered = [F1,F2|Rest].          % freebies occupy positions 1 & 2


/* compute cost for one particular choice of complimentary bags */
cost_for_choice(F1,F2,Total) :-
       ordered_list(F1,F2,Ordered),
       cost_bags(Ordered,1,CostBags,Penalties),
       flight_cost(Flight),
       Total is Flight + CostBags + Penalties.


/* walk through ordered list accumulating base fees and penalties */
cost_bags([],_,0,0).
cost_bags([Bag|Bs],Idx,CostSum,PenSum) :-
       (Idx =< 2 -> Type = comp ; Type = charged),
       bag_fee(Idx,Fee),
       penalty(Bag,Type,Pen),
       NextIdx is Idx+1,
       cost_bags(Bs,NextIdx,CostRest,PenRest),
       CostSum is Fee + CostRest,
       PenSum  is Pen + PenRest.



/* ============================================================
   Grand-total: minimal cost across all choices of freebies
   ============================================================ */
total_cost(MinTotal) :-
       checked_bag_ids(L),
       findall(T,
               ( choose_two(L,F1,F2),
                 cost_for_choice(F1,F2,T)),
               Totals),
       min_list(Totals,MinTotal).



/* ============================================================
   Query & output  (exactly as required)
   ============================================================ */
:- total_cost(Total), format('Total cost: ~w~n', [Total]).
:- halt.