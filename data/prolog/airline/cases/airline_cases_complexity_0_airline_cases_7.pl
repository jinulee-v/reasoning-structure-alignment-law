/* =========================================================
   Facts describing Elizabeth's itinerary and luggage
   ========================================================= */

/* ticket price */
flight_cost(471).

/* checked bags:  bag(Id,Length,Width,Height,Weight) */
bag(2,33,23, 9,56).
bag(3,49,27,20,52).
bag(4,37,17,10,58).
bag(5,50,35,30,53).

/* list of all checked-bag Ids */
checked_bag_ids([2,3,4,5]).

/* =========================================================
   Statutory rules for travel between the U.S. and India
   (First Class)
   ========================================================= */

/* sum of the 3 dimensions */
dims_sum(L,W,H,S) :- S is L+W+H.

/* ---------------------------------------------------------
   Over-SIZE fees   (China / Japan / S. Korea / HK / India /
                     Australia / New Zealand region)
   --------------------------------------------------------- */
oversize_fee(Sum,Fee) :-
      (  Sum =< 62      -> Fee = 0          % not oversize
      ;  Sum =< 65      -> Fee = 30         % 62-65 in
      ;  Sum =< 115     -> Fee = 200        % 65-115 in
      ).

/* ---------------------------------------------------------
   Over-WEIGHT fees
   Two different free allowances apply:
        - complimentary bag => 70-lb threshold
        - charged bag       => 50-lb threshold
   --------------------------------------------------------- */
overweight_fee(W,Thresh,Fee) :-
      (  W =< Thresh    -> Fee = 0
      ;  W =< 53        -> Fee = 30
      ;  W =< 70        -> Fee = 100
      ;  W =< 100       -> Fee = 450        % 70-100 lb  (India region)
      ).

/* ---------------------------------------------------------
   Penalty for a bag = higher of its oversize vs overweight
   --------------------------------------------------------- */
penalty(BagId,comp,Pen) :-
      bag(BagId,L,W,H,WT),
      dims_sum(L,W,H,S),
      oversize_fee(S,OS),
      overweight_fee(WT,70,OW),             % complimentary
      Pen is max(OS,OW).

penalty(BagId,charged,Pen) :-
      bag(BagId,L,W,H,WT),
      dims_sum(L,W,H,S),
      oversize_fee(S,OS),
      overweight_fee(WT,50,OW),             % charged
      Pen is max(OS,OW).

/* ---------------------------------------------------------
   Base checked-bag fee (First Class, U.S.-India):
        - 1st, 2nd, 3rd bags: $0
        - 4th bag and beyond : $200
   --------------------------------------------------------- */
bag_base_fee(N,Fee) :-
      (  N =< 3   -> Fee = 0
      ;  N >= 4   -> Fee = 200 ).

/* =========================================================
   Helper predicates
   ========================================================= */

/* choose exactly 1 bag that will become the (charged) 4th bag */
choose_one(List,Chosen) :- member(Chosen,List).

/* build the ordered list: complimentary bags first, charged bag last */
ordered_list(Charged,Ordered) :-
      checked_bag_ids(All),
      select(Charged,All,Complimentary),
      append(Complimentary,[Charged],Ordered).

/* walk the ordered list, accumulating base fees and penalties */
cost_bags([],_,0).
cost_bags([Bag|Rest],Idx,TotalCost) :-
      ( Idx =< 3 -> Type = comp ; Type = charged ),
      bag_base_fee(Idx,Base),
      penalty(Bag,Type,Pen),
      NextIdx is Idx + 1,
      cost_bags(Rest,NextIdx,RestCost),
      TotalCost is Base + Pen + RestCost.

/* total cost for a particular choice of charged bag */
cost_for_choice(Charged,Total) :-
      ordered_list(Charged,Ordered),
      cost_bags(Ordered,1,BagCost),
      flight_cost(Tix),
      Total is Tix + BagCost.

/* compute the minimal total cost over all possible choices */
total_cost(MinTotal) :-
      checked_bag_ids(L),
      findall(T, (choose_one(L,Ch), cost_for_choice(Ch,T)), Totals),
      min_list(Totals,MinTotal).

/* =========================================================
   Query and output
   ========================================================= */
compute_total(Cost) :- total_cost(Cost).
:- compute_total(Cost), format('Total cost: ~w~n', [Cost]), halt.