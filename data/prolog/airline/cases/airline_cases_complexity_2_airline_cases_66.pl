:- format("~w~n", ["Label: 5039"]).
/* =========================================================
   American Airlines bag-fee calculator
   Case: Charles - Business Class, Washington-D.C. -> Shanghai
   ========================================================= */

/* ---------------  Ticket price  -------------------------- */
flight_cost(969).


/* ---------------  Bags carried  -------------------------- */

/* carry-on (free, so not listed among checked bags)
   bag(1,22,14,8,11). */

/* checked bags: bag(Id,Length,Width,Height,Weight) */
bag(2,36,14,13,91).
bag(3,36,19, 9,53).
bag(4,33,17,14,51).
bag(5,51,30,24,86).
bag(6,34,17,12,71).
bag(7,38,18, 9,64).
bag(8,34,18,13,57).
bag(9,34,20,11,59).
bag(10,35,17,13,80).
bag(11,45,26,17,77).

/* list of all checked-bag Ids */
checked_bag_ids([2,3,4,5,6,7,8,9,10,11]).

/* ---------------  Statutory rules for this itinerary ----- */

/* Sum of dimensions */
dims_sum(L,W,H,S) :- S is L+W+H.

/* Oversize fee - to / from China                         */
/* 0  : =<62 in                                            */
/* 30 : 62-65 in                                          */
/* 200: 65-115 in                                         */
oversize_fee(Sum,Fee) :-
         (   Sum =< 62      -> Fee = 0
         ;   Sum =< 65      -> Fee = 30
         ;   Sum =< 115     -> Fee = 200 ).

/* Over-weight fee - to / from China                                */
/* Thresh = 70 lb for complimentary bags, 50 lb for charged bags.   */
/*  0   : =< Thresh                                                  */
/* 30   : >Thresh - 53 lb                                           */
/* 100  : 53-70 lb                                                  */
/* 450  : 70-100 lb                                                 */
overweight_fee(W,Thresh,Fee) :-
         (   W =< Thresh        -> Fee = 0
         ;   W =< 53            -> Fee = 30
         ;   W =< 70            -> Fee = 100
         ;   W =< 100           -> Fee = 450 ).

/* Penalty = higher of oversize vs overweight */
penalty(BagId,comp,Pen) :-
         bag(BagId,L,W,H,Weight),
         dims_sum(L,W,H,Sum),
         oversize_fee(Sum,OS),
         overweight_fee(Weight,70,OW),      % complimentary -> 70-lb limit
         Pen is max(OS,OW).

penalty(BagId,charged,Pen) :-
         bag(BagId,L,W,H,Weight),
         dims_sum(L,W,H,Sum),
         oversize_fee(Sum,OS),
         overweight_fee(Weight,50,OW),      % charged bag -> 50-lb limit
         Pen is max(OS,OW).

/* Checked-bag base fee by ordinal position (Business class,
   U.S. <-> China)                                                */
bag_fee(1,0).
bag_fee(2,0).
bag_fee(N,200) :- N>=3.

/* ---------------  Helper predicates --------------------- */

/* choose two different elements (F1<F2) from a list */
choose_two(List,F1,F2) :-
         append(_,[F1|Tail],List),
         member(F2,Tail).

/* remove the chosen freebies and build the ordered list:
      freebies are placed in positions 1 & 2                */
ordered_list(F1,F2,Ordered) :-
         checked_bag_ids(All),
         select(F1,All,Rest1),
         select(F2,Rest1,Rest),
         Ordered = [F1,F2|Rest].

/* Cost for a particular choice of the 2 complimentary bags */
cost_for_choice(F1,F2,Total) :-
         ordered_list(F1,F2,Ordered),
         cost_bags(Ordered,1,CostBags,Penalties),
         flight_cost(Flight),
         Total is Flight + CostBags + Penalties.

/* Walk through ordered list accumulating base fees & penalties */
cost_bags([],_,0,0).
cost_bags([Bag|Bs],Idx,CostSum,PenSum) :-
         (Idx =< 2 -> Type = comp ; Type = charged),
         bag_fee(Idx,Base),
         penalty(Bag,Type,Pen),
         Next is Idx+1,
         cost_bags(Bs,Next,CostRest,PenRest),
         CostSum is Base + CostRest,
         PenSum  is Pen  + PenRest.

/* Compute minimal total cost over all ways of selecting 2 freebies */
total_cost(MinTotal) :-
         checked_bag_ids(L),
         findall(T,
                 ( choose_two(L,F1,F2),
                   cost_for_choice(F1,F2,T)),
                 Totals),
         min_list(Totals,MinTotal).

/* ---------------  Query & output ------------------------- */
:- total_cost(Total), format('Total cost: ~w~n',[Total]).
:- halt.