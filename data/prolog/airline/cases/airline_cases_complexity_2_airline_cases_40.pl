:- format("~w~n", ["Label: 3768"]).
/* =========================================================
   American Airlines baggage calculation
   Case: Sarah - Business Class, Mumbai (India) -> Portland
   Ticket price : $518
   ========================================================= */

/* --------------- Ticket ----------------------------- */
flight_cost(518).

/* --------------- Checked bags ----------------------- */
/* bag(Id,Length,Width,Height,Weight) - carry-on bag (Id 1)
   is within the cabin allowance so it is *not* listed here. */
bag(2,48,27,21,51).
bag(3,33,21, 9,52).
bag(4,37,17, 9,97).
bag(5,45,27,18,54).
bag(6,38,17, 9,52).
bag(7,35,16,14,86).
bag(8,39,26,18,52).
bag(9,35,20, 9,55).
bag(10,38,13,13,51).
bag(11,38,11,14,51).

/* list of all checked-bag Ids */
checked_bag_ids([2,3,4,5,6,7,8,9,10,11]).

/* --------------- Size and weight helpers ------------ */
dims_sum(L,W,H,S) :- S is L+W+H.

/* Oversize fees - India / Asia group */
oversize_fee(Sum,Fee) :-
      ( Sum =< 62  -> Fee = 0
      ; Sum =< 65  -> Fee = 30
      ; Sum =< 115 -> Fee = 200 ).

/* Overweight fees - India routes                        */
/* Thresh is the free allowance (70 lb for complimentary,
   50 lb for charged bags)                               */
overweight_fee(W,Thresh,Fee) :-
      ( W =< Thresh -> Fee = 0
      ; W =< 53     -> Fee = 30
      ; W =< 70     -> Fee = 100
      ; W =< 100    -> Fee = 450 ).

/* --------------- Penalty (oversize / overweight) ---- */
penalty(BagId,comp,Pen) :-
      bag(BagId,L,W,H,Weight),
      dims_sum(L,W,H,Sum),
      oversize_fee(Sum,OS),
      overweight_fee(Weight,70,OW),      % 70-lb limit for freebies
      Pen is max(OS,OW).

penalty(BagId,charged,Pen) :-
      bag(BagId,L,W,H,Weight),
      dims_sum(L,W,H,Sum),
      oversize_fee(Sum,OS),
      overweight_fee(Weight,50,OW),      % 50-lb limit for charged bags
      Pen is max(OS,OW).

/* --------------- Base checked-bag fees --------------- */
/* Business Class - to / from India                      */
bag_fee(1,0).
bag_fee(2,0).
bag_fee(N,200) :- N>=3.

/* --------------- Utilities --------------------------- */
choose_two(List,F1,F2) :-
      append(_,[F1|Tail],List),
      member(F2,Tail).

ordered_list(F1,F2,Ordered) :-
      checked_bag_ids(All),
      select(F1,All,Rest1),
      select(F2,Rest1,Rest),
      Ordered = [F1,F2|Rest].            % freebies occupy slots 1 & 2

/* cost for one particular choice of complimentary bags */
cost_for_choice(F1,F2,Total) :-
      ordered_list(F1,F2,Ordered),
      cost_bags(Ordered,1,CostBags,Penalties),
      flight_cost(Flight),
      Total is Flight + CostBags + Penalties.

/* walk through the ordered list, adding up fees */
cost_bags([],_,0,0).
cost_bags([Bag|Bs],Idx,CostSum,PenSum) :-
      (Idx =< 2 -> Type = comp ; Type = charged),
      bag_fee(Idx,Fee),
      penalty(Bag,Type,Pen),
      NextIdx is Idx+1,
      cost_bags(Bs,NextIdx,CostRest,PenRest),
      CostSum is Fee + CostRest,
      PenSum  is Pen + PenRest.

/* --------------- Overall minimum -------------------- */
total_cost(MinTotal) :-
      checked_bag_ids(L),
      findall(T,
              ( choose_two(L,F1,F2),
                cost_for_choice(F1,F2,T)),
              Totals),
      min_list(Totals,MinTotal).

/* --------------- Query & output --------------------- */
:- total_cost(Total), format('Total cost: ~w~n', [Total]).
:- halt.