:- format("~w~n", ["Label: 972"]).
/* =========================================
   Susan - Minneapolis (MSP) -> Miami (MIA)
   Business Class - domestic itinerary
   ========================================= */

/* ---------- ticket price ---------------- */
flight_cost(162).

/* ---------- checked bags ---------------- */
/* bag(Id, Length, Width, Height, Weight)   */
bag(2, 44, 32, 20, 51).
bag(3, 37, 13, 14, 68).
bag(4, 34, 16, 14, 66).
bag(5, 49, 32, 23, 96).

/* list of *checked* bag Ids                */
checked_bag_ids([2,3,4,5]).

/* ---------- statutory rules -------------- */

/* sum of the 3 outside dimensions */
dims_sum(L,W,H,S) :- S is L+W+H.

/* oversize fee - within / between U.S. & Canada */
oversize_fee(S,Fee) :-
         (   S =< 62  -> Fee = 0
         ;   S =< 65  -> Fee = 30
         ;   S =< 115 -> Fee = 200 ).

/* overweight fee - threshold = 70 lb for complimentary,
                      threshold = 50 lb for charged bags  */
overweight_fee(W,Thresh,Fee) :-
         (   W =< Thresh -> Fee = 0
         ;   W =< 53     -> Fee = 30
         ;   W =< 70     -> Fee = 100
         ;   W =< 100    -> Fee = 200 ).

/* penalty = higher of oversize vs. overweight ------------- */
penalty(BagId,complimentary,Pen) :-
         bag(BagId,L,W,H,Wt),
         dims_sum(L,W,H,Sum),
         oversize_fee(Sum,OS),
         overweight_fee(Wt,70,OW),
         Pen is max(OS,OW).

penalty(BagId,charged,Pen) :-
         bag(BagId,L,W,H,Wt),
         dims_sum(L,W,H,Sum),
         oversize_fee(Sum,OS),
         overweight_fee(Wt,50,OW),
         Pen is max(OS,OW).

/* base checked-bag fees for Business Class, domestic */
bag_fee(1,0).
bag_fee(2,0).
bag_fee(3,150).
bag_fee(N,200) :- N >= 4.

/* ---------- helper predicates ------------- */

/* choose two distinct elements (F1 < F2) from a list */
choose_two(List,F1,F2) :-
         append(_,[F1|Tail],List),
         member(F2,Tail).

/* place freebies first, preserve order of the others */
ordered_list(F1,F2,Ordered) :-
         checked_bag_ids(All),
         select(F1,All,R1),
         select(F2,R1,R2),
         Ordered = [F1,F2|R2].

/* cost for one specific choice of the two complimentary bags */
cost_for_choice(F1,F2,Total) :-
         ordered_list(F1,F2,Ordered),
         cost_bags(Ordered,1,BagCost,Penalties),
         flight_cost(Flight),
         Total is Flight + BagCost + Penalties.

/* walk through ordered list accumulating base fees & penalties */
cost_bags([],_,0,0).
cost_bags([Bag|Bs],Idx,CostSum,PenSum) :-
         (Idx =< 2 -> Class = complimentary ; Class = charged),
         bag_fee(Idx,BaseFee),
         penalty(Bag,Class,Pen),
         NextIdx is Idx+1,
         cost_bags(Bs,NextIdx,RestCost,RestPen),
         CostSum is BaseFee + RestCost,
         PenSum  is Pen + RestPen.

/* compute minimal total over every way of picking 2 freebies */
total_cost(MinTotal) :-
         checked_bag_ids(L),
         findall(T,
                 ( choose_two(L,F1,F2),
                   cost_for_choice(F1,F2,T) ),
                 Totals),
         min_list(Totals,MinTotal).

/* ---------- query & output ---------------- */
:- total_cost(Total), format('Total cost: ~w~n',[Total]).
:- halt.