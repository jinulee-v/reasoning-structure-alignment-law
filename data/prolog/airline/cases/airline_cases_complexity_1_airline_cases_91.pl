/* ----------  Trip facts (Patricia)  --------------------------- */

/* ticket price */
flight_cost(1154).

/* checked bags: bag(Id,Length,Width,Height,Weight)              */
/* (carry-on item #1 is omitted - it isn't checked)               */
bag(2,37,12,14,54).
bag(3,36,14,14,53).
bag(4,34,19,12,77).
bag(5,52,34,28,59).
bag(6,40,26,20,69).
bag(7,37,12,14,54).
bag(8,52,33,26,57).

/* list of all checked-bag Ids, in no particular order            */
checked_bag_ids([2,3,4,5,6,7,8]).

/* ----------  Statutory rules for SFO-China (Business) --------- */

/* sum of the 3 outside dimensions */
dims_sum(L,W,H,S) :- S is L+W+H.

/* oversize fees - China / Hong Kong / India / Japan ... region */
oversize_fee(Sum,Fee) :-
       (   Sum =< 62  -> Fee = 0
       ;   Sum =< 65  -> Fee = 30
       ;   Sum =< 115 -> Fee = 200 ).

/* overweight fees - same region
   Thresh is 70 lbs for complimentary bags, 50 lbs for charged bags  */
overweight_fee(W,Thresh,Fee) :-
       (   W =< Thresh -> Fee = 0
       ;   W =< 53     -> Fee = 30
       ;   W =< 70     -> Fee = 100
       ;   W =< 100    -> Fee = 450 ).

/* penalty for a bag = higher of oversize vs overweight */
penalty(BagId,comp,Pen) :-
       bag(BagId,L,W,H,Weight),
       dims_sum(L,W,H,Sum),
       oversize_fee(Sum,OS),
       overweight_fee(Weight,70,OW),          /* complimentary => 70-lb limit */
       Pen is max(OS,OW).

penalty(BagId,charged,Pen) :-
       bag(BagId,L,W,H,Weight),
       dims_sum(L,W,H,Sum),
       oversize_fee(Sum,OS),
       overweight_fee(Weight,50,OW),          /* charged bag => 50-lb limit   */
       Pen is max(OS,OW).

/* base checked-bag fee (Business, to / from China) */
bag_fee(1,0).
bag_fee(2,0).
bag_fee(3,200).
bag_fee(N,200) :- N>=4.

/* ----------  Helper predicates -------------------------------- */

/* choose 2 distinct elements (F1 < F2) from a list */
choose_two(List,F1,F2) :-
       append(_,[F1|Tail],List),
       member(F2,Tail).

/* put the 2 free bags first, keep order for the rest */
ordered_list(F1,F2,Ordered) :-
       checked_bag_ids(All),
       select(F1,All,Rest1),
       select(F2,Rest1,Rest),
       Ordered = [F1,F2|Rest].

/* cost for one particular choice of free bags */
cost_for_choice(F1,F2,Total) :-
       ordered_list(F1,F2,Ordered),
       cost_bags(Ordered,1,BagFees,PenFees),
       flight_cost(Tix),
       Total is Tix + BagFees + PenFees.

/* walk the ordered list, accumulating fees and penalties */
cost_bags([],_,0,0).
cost_bags([Bag|Bs],Idx,SumFees,SumPen) :-
       (Idx =< 2 -> Type = comp ; Type = charged),
       bag_fee(Idx,Fee),
       penalty(Bag,Type,Pen),
       NextIdx is Idx + 1,
       cost_bags(Bs,NextIdx,FeesRest,PenRest),
       SumFees is Fee + FeesRest,
       SumPen  is Pen + PenRest.

/* minimal total over all ways of selecting the 2 complimentary bags */
compute_total(MinTotal) :-
       checked_bag_ids(L),
       findall(T,
               ( choose_two(L,F1,F2),
                 cost_for_choice(F1,F2,T)),
               Totals),
       min_list(Totals,MinTotal).

/* ----------  Query and output --------------------------------- */
:- compute_total(Cost), format('Total cost: ~w~n', [Cost]), halt.