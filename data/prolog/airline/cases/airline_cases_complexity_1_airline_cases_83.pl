:- format("~w~n", ["Label: 2266"]).
/* -------------  Facts describing James' trip -------------------- */

/* ticket price */
flight_cost(696).

/* list of checked bags:  bag(Id,Length,Width,Height,Weight).       */
bag(2,35,18,12,67).
bag(3,38,15,12,70).
bag(4,51,36,27,51).
bag(5,36,15,12,52).
bag(6,48,29,27,52).
bag(7,33,21, 9,51).
bag(8,37,17,14,70).

/* list of all checked-bag Ids (carry-on bag #1 is excluded)        */
checked_bag_ids([2,3,4,5,6,7,8]).

/* -------------  Statutory rules for this itinerary -------------- */

/* sum of dimensions */
dims_sum(L,W,H,S) :- S is L+W+H.

/* oversize fee - between Europe and U.S.                            */
/*   =<62 in       : $0                                               */
/*   62-65 in     : $30                                              */
/*   65-115 in    : $150                                             */
oversize_fee(Sum,Fee) :-
       (  Sum =< 62       -> Fee = 0
       ;  Sum =< 65       -> Fee = 30
       ;  Sum =< 115      -> Fee = 150 ).

/* overweight fee (all regions)                                     */
/* Thresh = max weight (lbs) allowed before a fee is charged         */
overweight_fee(W,Thresh,Fee) :-
       (  W =< Thresh     -> Fee = 0
       ;  W =< 53         -> Fee = 30
       ;  W =< 70         -> Fee = 100
       ;  W =< 100        -> Fee = 200 ).

/* penalty = higher of oversize vs. overweight                      */
/* Complimentary bags use Thresh 70; charged bags use Thresh 50     */
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

/* checked-bag fees for Business Class, Europe<->U.S. route            */
bag_fee(1,0).
bag_fee(2,0).
bag_fee(N,200) :- N>=3.

/* -------------  Helper predicates --------------------------------*/

/* choose two different elements (F1<F2) from a list                 */
choose_two(List,F1,F2) :-
       append(_,[F1|Tail],List),
       member(F2,Tail).

/* create ordered list: the 2 freebies occupy positions 1 and 2      */
ordered_list(F1,F2,Ordered) :-
       checked_bag_ids(All),
       select(F1,All,R1),
       select(F2,R1,Rest),
       Ordered = [F1,F2|Rest].

/* cost for a particular choice of complimentary bags                */
cost_for_choice(F1,F2,Total) :-
       ordered_list(F1,F2,Ordered),
       cost_bags(Ordered,1,CostBags,Penalties),
       flight_cost(Flight),
       Total is Flight + CostBags + Penalties.

/* walk through ordered list accumulating bag fees and penalties     */
cost_bags([],_,0,0).
cost_bags([Bag|Bs],Idx,CostSum,PenSum) :-
       (Idx =< 2 -> Type = comp ; Type = charged),
       bag_fee(Idx,Fee),
       penalty(Bag,Type,Pen),
       Next is Idx+1,
       cost_bags(Bs,Next,Cs,Ps),
       CostSum is Fee + Cs,
       PenSum  is Pen + Ps.

/* minimal total cost over all possible selections of 2 free bags    */
total_cost(MinTotal) :-
       checked_bag_ids(L),
       findall(T,
               ( choose_two(L,F1,F2),
                 cost_for_choice(F1,F2,T)),
               Totals),
       min_list(Totals,MinTotal).

/* -------------  Query and output --------------------------------- */
:- total_cost(Total), format('Total cost: ~w~n', [Total]).
:- halt.