/* ----------------------------------------------------------
   Facts describing Daniel's trip
   ---------------------------------------------------------- */

/* ticket price */
flight_cost(343).

/* checked bags: bag(Id,Length,Width,Height,Weight) */
bag(2,33,19,13,58).
bag(3,39,26,15,60).
bag(4,41,24,22,59).
bag(5,33,17,13,66).

/* list (constant) of all checked-bag Ids */
checked_bag_ids([2,3,4,5]).

/* ----------------------------------------------------------
   Statutory rules that apply to this itinerary
   (First Class - between U.S. and Europe)
   ---------------------------------------------------------- */

/* utility: sum of dimensions */
dims_sum(L,W,H,S) :- S is L+W+H.

/* oversize fees - Europe  <-->  U.S. */
oversize_fee(Sum,Fee) :-
       (   Sum =< 62      -> Fee = 0
       ;   Sum =< 65      -> Fee = 30
       ;   Sum =< 115     -> Fee = 150 ).

/* overweight fees (lbs). 'Thresh' is free allowance:
     70 lbs for complimentary bags
     50 lbs for charged bags                                       */
overweight_fee(W,Thresh,Fee) :-
       (   W =< Thresh        -> Fee = 0
       ;   W =< 53            -> Fee = 30
       ;   W =< 70            -> Fee = 100
       ;   W =< 100           -> Fee = 200 ).

/* penalty for a bag = max(oversize, overweight) */
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

/* base checked-bag fees (First Class - U.S./Europe) */
bag_fee(1,0).
bag_fee(2,0).
bag_fee(3,0).
bag_fee(4,200).
bag_fee(N,200) :- N>=4.

/* ----------------------------------------------------------
   Helper predicates
   ---------------------------------------------------------- */

/* select 1 bag that will be the (charged) 4th bag */
choose_charged(List,Charged) :-
       member(Charged,List).

/* put chosen charged bag last to obtain ordered list */
ordered_list(Charged,Ordered) :-
       checked_bag_ids(All),
       select(Charged,All,Free),
       append(Free,[Charged],Ordered).

/* cost for a particular choice of charged bag */
cost_for_choice(Charged,Total) :-
       ordered_list(Charged,Ordered),
       cost_bags(Ordered,1,CostBags,Penalties),
       flight_cost(Flight),
       Total is Flight + CostBags + Penalties.

/* walk through ordered list accumulating fees & penalties */
cost_bags([],_,0,0).
cost_bags([Bag|Bs],Idx,CostSum,PenSum) :-
       (Idx =< 3 -> Type = comp ; Type = charged),
       bag_fee(Idx,Fee),
       penalty(Bag,Type,Pen),
       Next is Idx+1,
       cost_bags(Bs,Next,RestCost,RestPen),
       CostSum is Fee + RestCost,
       PenSum  is Pen + RestPen.

/* minimal total cost over all ways of picking the charged bag */
total_cost(MinTotal) :-
       checked_bag_ids(L),
       findall(T,
               ( choose_charged(L,Charged),
                 cost_for_choice(Charged,T)),
               Totals),
       min_list(Totals,MinTotal).

/* ----------------------------------------------------------
   Query & output
   ---------------------------------------------------------- */
:- total_cost(Total), format('Total cost: ~w~n',[Total]).
:- halt.