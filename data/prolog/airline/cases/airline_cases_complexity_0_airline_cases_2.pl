/* =================  Facts describing Linda's trip  ================= */

/* ticket price */
flight_cost(186).

/* cabin class */
cabin_class(business).

/* checked luggage:  bag(Id,Length,Width,Height,Weight) */
bag(2,41,20,16,95).
bag(3,38,24,18,74).
bag(4,37,16,10,54).
bag(5,43,25,20,52).

/* list of all checked-bag Ids (carry-on isn't listed) */
checked_bag_ids([2,3,4,5]).

/* =================  Statutory rules for this itinerary  ============= */

/* sum of the 3 dimensions */
dims_sum(L,W,H,S) :- S is L+W+H.

/* oversize fee - travel within / between U.S. / Canada / PR / USVI */
oversize_fee(Sum,Fee) :-
       (   Sum =< 62      -> Fee = 0
       ;   Sum =< 65      -> Fee = 30
       ;   Sum =< 115     -> Fee = 200 ).

/* overweight fee - within / between U.S. / Canada / PR / USVI       */
/* complimentary bags: 70-lb limit; charged bags: 50-lb limit        */
overweight_fee(W,Thresh,Fee) :-
       (   W =< Thresh        -> Fee = 0
       ;   W =< 53            -> Fee = 30
       ;   W =< 70            -> Fee = 100
       ;   W =< 100           -> Fee = 200 ).

/* penalty for a bag = higher of oversize vs overweight fee */
penalty(BagId,comp,Pen) :-
       bag(BagId,L,W,H,Weight),
       dims_sum(L,W,H,Sum),
       oversize_fee(Sum,OS),
       overweight_fee(Weight,70,OW),           % complimentary => 70-lb limit
       Pen is max(OS,OW).

penalty(BagId,charged,Pen) :-
       bag(BagId,L,W,H,Weight),
       dims_sum(L,W,H,Sum),
       oversize_fee(Sum,OS),
       overweight_fee(Weight,50,OW),           % charged bag => 50-lb limit
       Pen is max(OS,OW).

/* checked-bag base fee by ordinal position for Business Class, domestic */
bag_fee(1,0).
bag_fee(2,0).
bag_fee(3,150).
bag_fee(N,200) :- N>=4.

/* =================  Helper predicates  ============================= */

/* choose 2 distinct elements (F1 < F2) from a list */
choose_two(List,F1,F2) :-
       append(_,[F1|Tail],List),
       member(F2,Tail).

/* build the ordered list: freebies occupy positions 1 and 2 */
ordered_list(F1,F2,Ordered) :-
       checked_bag_ids(All),
       select(F1,All,R1),
       select(F2,R1,Rest),
       Ordered = [F1,F2|Rest].

/* compute cost for a particular choice of complimentary bags */
cost_for_choice(F1,F2,Total) :-
       ordered_list(F1,F2,Ordered),
       cost_bags(Ordered,1,BagBaseFees,Penalties),
       flight_cost(Flight),
       Total is Flight + BagBaseFees + Penalties.

/* walk through ordered list accumulating base fees and penalties */
cost_bags([],_,0,0).
cost_bags([Bag|Bs],Idx,FeeSum,PenSum) :-
       (Idx =< 2 -> Type = comp ; Type = charged),
       bag_fee(Idx,Base),
       penalty(Bag,Type,Pen),
       NextIdx is Idx + 1,
       cost_bags(Bs,NextIdx,RestBase,RestPen),
       FeeSum is Base + RestBase,
       PenSum  is Pen  + RestPen.

/* minimal total cost over all ways of selecting 2 complimentary bags */
compute_total(MinTotal) :-
       checked_bag_ids(L),
       findall(Total,
               ( choose_two(L,F1,F2),
                 cost_for_choice(F1,F2,Total)),
               Totals),
       min_list(Totals,MinTotal).

/* =================  Query and output  ============================== */
:- compute_total(Cost), format('Total cost: ~w~n', [Cost]), halt.