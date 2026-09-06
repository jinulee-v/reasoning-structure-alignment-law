:- format("~w~n", ["Label: 2375"]).
/* ================================================================
   American Airlines baggage-fee calculator
   Case:  Jessica - Premium Economy, Boston (U.S.) -> Sydney (Australia)
   ================================================================ */

/* ----------------  Basic trip facts  --------------------------- */

/* ticket price */
flight_cost(825).

/* list of checked bags
      bag(Id,Length,Width,Height,Weight).                        */
bag(2,47,26,20,66).
bag(3,34,20, 9,64).
bag(4,34,19,11,53).
bag(5,50,32,25,66).
bag(6,35,16,14,62).
bag(7,33,21, 9,51).
bag(8,36,20, 9,52).

/* list (constant) of all checked-bag Ids (carry-on bag #1 excluded) */
checked_bag_ids([2,3,4,5,6,7,8]).

/* ----------------  Statutory rules (U.S. <-> Australia) ---------- */

/* algebraic sum of dimensions */
dims_sum(L,W,H,S) :- S is L+W+H.

/*  Oversize fee:   China / Japan / Korea / HK / India / AUS / NZ  */
oversize_fee(Sum,Fee) :-
       (   Sum =< 62      -> Fee = 0
       ;   Sum =< 65      -> Fee = 30
       ;   Sum =< 115     -> Fee = 200 ).

/*  Over-weight fee (all regions) - 'Thresh' = gratis weight limit */
overweight_fee(W,Thresh,Fee) :-
       (   W =< Thresh        -> Fee = 0
       ;   W =< 53            -> Fee = 30
       ;   W =< 70            -> Fee = 100
       ;   W =< 100           -> Fee = 200 ).

/*  Penalty = higher of oversize vs overweight                    */
penalty(BagId,comp,Pen) :-
       bag(BagId,L,W,H,Wgt),
       dims_sum(L,W,H,Sum),
       oversize_fee(Sum,OS),
       overweight_fee(Wgt,70,OW),          % complimentary => 70-lb limit
       Pen is max(OS,OW).

penalty(BagId,charged,Pen) :-
       bag(BagId,L,W,H,Wgt),
       dims_sum(L,W,H,Sum),
       oversize_fee(Sum,OS),
       overweight_fee(Wgt,50,OW),          % charged bag => 50-lb limit
       Pen is max(OS,OW).

/*  Base checked-bag fee for Premium Economy on U.S.-Australia     */
bag_fee(1,0).             % 1st bag free
bag_fee(2,0).             % 2nd bag free
bag_fee(3,200).
bag_fee(N,200) :- N>=4.

/* ----------------  Helper predicates  -------------------------- */

/* choose 2 distinct freebies (F1<F2) from the bag list            */
choose_two(List,F1,F2) :-
       append(_,[F1|Tail],List),
       member(F2,Tail).

/* place freebies first, preserve order of the remainder           */
ordered_list(F1,F2,Ordered) :-
       checked_bag_ids(All),
       select(F1,All,R1),
       select(F2,R1,Remainder),
       Ordered = [F1,F2|Remainder].

/* cost for a particular choice of complimentary bags              */
cost_for_choice(F1,F2,Total) :-
       ordered_list(F1,F2,Ordered),
       cost_bags(Ordered,1,BagCost,PenCost),
       flight_cost(Flight),
       Total is Flight + BagCost + PenCost.

/* walk through ordered list accumulating base fees + penalties    */
cost_bags([],_,0,0).
cost_bags([Bag|Bs],Idx,BagSum,PenSum) :-
       (Idx =< 2 -> Type = comp ; Type = charged),
       bag_fee(Idx,Fee),
       penalty(Bag,Type,Pen),
       Next is Idx+1,
       cost_bags(Bs,Next,BRest,PRest),
       BagSum is Fee + BRest,
       PenSum is Pen + PRest.

/*  Minimum total over all ways of selecting 2 complimentary bags  */
total_cost(MinTotal) :-
       checked_bag_ids(L),
       findall(T,
               ( choose_two(L,F1,F2),
                 cost_for_choice(F1,F2,T)),
               Totals),
       min_list(Totals,MinTotal).

/* ----------------  Query & output ------------------------------ */
:- total_cost(Total), format('Total cost: ~w~n', [Total]).
:- halt.