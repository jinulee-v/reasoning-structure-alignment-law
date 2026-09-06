:- format("~w~n", ["Label: 695"]).
/* ===========================================================
   Patricia - Philadelphia (U.S.)  ->  Paris (France)
   Cabin: First Class   -  Trans-Atlantic itinerary
   ===========================================================*/

/* ----------------  Ticket price  ---------------------------*/
flight_cost(255).

/* ----------------  Baggage data  ---------------------------*/
/* Bag facts: bag(Id,Length,Width,Height,Weight).            */
/* Bag 1 is carry-on (22*14*9 / 12 lbs) and is therefore not */
/* included in the checked-bag list.                         */

bag(2,35,18,10,51).
bag(3,41,20,14,53).
bag(4,38,16, 9,52).
bag(5,36,17,12,59).

/* list of checked-bag Ids (all except the carry-on) */
checked_bag_ids([2,3,4,5]).

/* ----------------  Statutory rules  -------------------------*/

/* ------ size: sum of the three outside dimensions ----------*/
dims_sum(L,W,H,S) :- S is L+W+H.

/* ------ oversize fees (Europe <-> U.S.) ----------------------*/
/* 0 - 62 in => $0 | 62+ - 65 in => $30 | 65+ - 115 in => $150   */
oversize_fee(Sum,Fee) :-
      (  Sum =< 62      -> Fee = 0
      ;  Sum =< 65      -> Fee = 30
      ;  Sum =< 115     -> Fee = 150).

/* ------ overweight fees ------------------------------------*/
/* Thresh is weight allowance (70 lbs for complimentary bags,
   50 lbs for charged bags).                                  */
overweight_fee(W,Thresh,Fee) :-
      (  W =< Thresh    -> Fee = 0
      ;  W =< 53        -> Fee = 30
      ;  W =< 70        -> Fee = 100
      ;  W =< 100       -> Fee = 200).

/* ------ penalty: higher of the two (size vs weight) --------*/
penalty(BagId,comp,Pen) :-
      bag(BagId,L,W,H,Weight),
      dims_sum(L,W,H,Sum),
      oversize_fee(Sum,OS),
      overweight_fee(Weight,70,OW),      % 70-lb limit for gratis bags
      Pen is max(OS,OW).

penalty(BagId,charged,Pen) :-
      bag(BagId,L,W,H,Weight),
      dims_sum(L,W,H,Sum),
      oversize_fee(Sum,OS),
      overweight_fee(Weight,50,OW),      % 50-lb limit for charged bags
      Pen is max(OS,OW).

/* ------ base checked-bag fees for First Class --------------*/
/* 1st, 2nd, 3rd bags: $0   |   4th+ bags: $200               */
bag_fee(1,0).
bag_fee(2,0).
bag_fee(3,0).
bag_fee(N,200) :- N >= 4.

/* ----------------  Helper predicates  -----------------------*/

/* choose exactly 1 bag to be the "paid" 4th bag               */
choose_paid(List,Paid,Ordered) :-
        select(Paid,List,Freebies),          % remove Paid from List
        append(Freebies,[Paid],Ordered).     % freebies first, paid last

/* compute total cost for a particular choice of paid bag      */
cost_for_choice(Paid,Total) :-
        checked_bag_ids(All),
        choose_paid(All,Paid,Ordered),
        cost_bags(Ordered,1,BagFees,Penalties),
        flight_cost(Flight),
        Total is Flight + BagFees + Penalties.

/* walk through ordered list, accumulating fees & penalties    */
cost_bags([],_,0,0).
cost_bags([Bag|Bs],Idx,CostSum,PenSum) :-
        (Idx =< 3 -> Type = comp ; Type = charged),
        bag_fee(Idx,Fee),
        penalty(Bag,Type,Pen),
        NextIdx is Idx + 1,
        cost_bags(Bs,NextIdx,CostRest,PenRest),
        CostSum is Fee + CostRest,
        PenSum  is Pen + PenRest.

/* --------------  Grand-total (minimised)  -------------------*/
total_cost(MinTotal) :-
        checked_bag_ids(L),
        findall(T, (member(Paid,L), cost_for_choice(Paid,T)), Totals),
        min_list(Totals,MinTotal).

/* ----------------  Query & report  --------------------------*/
:- total_cost(Total), format('Total cost: ~w~n', [Total]).
:- halt.