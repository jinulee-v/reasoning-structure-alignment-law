:- format("~w~n", ["Label: 991"]).
/* ================================================================== */
/*  Karen - Business Class - Miami (U.S.)  ->  Montreal (Canada)       */
/*  Statutory calculation of the total trip cost                      */
/*  (2 complimentary checked bags for Business Class)                 */
/* ================================================================== */


/* -------------  Basic trip data  ---------------------------------- */

flight_cost(181).                     /* ticket price - USD */


/* list of checked bags:  bag(Id,Length,Width,Height,Weight)          */
/* (the small 18*12*7 in / 7-lb backpack is her free carry-on item)   */
bag(2,39,17,13,67).
bag(3,34,22, 9,54).
bag(4,38,16,10,53).
bag(5,36,20, 9,95).

checked_bag_ids([2,3,4,5]).           /* only the bags that are checked */


/* -------------  Statutory fee schedules  -------------------------- */

/* sum of a bag's outside dimensions */
dims_sum(L,W,H,S) :- S is L+W+H.

/* oversize fee - within / between the U.S. and Canada                */
oversize_fee(Sum,Fee) :-
       (   Sum =< 62      -> Fee = 0
       ;   Sum =< 65      -> Fee = 30
       ;   Sum =< 115     -> Fee = 200 ).

/* overweight fee                                                     */
/*  - Thresh = 70 lb for complimentary bags (1st & 2nd)               */
/*  - Thresh = 50 lb for charged bags (3rd and after)                 */
overweight_fee(W,Thresh,Fee) :-
       (   W =< Thresh        -> Fee = 0
       ;   W =< 53            -> Fee = 30
       ;   W =< 70            -> Fee = 100
       ;   W =< 100           -> Fee = 200 ).

/* penalty for a bag = higher of oversize vs. overweight              */
penalty(BagId,comp,Pen) :-
       bag(BagId,L,W,H,Wt),
       dims_sum(L,W,H,S),
       oversize_fee(S,OS),
       overweight_fee(Wt,70,OW),           % complimentary threshold
       Pen is max(OS,OW).

penalty(BagId,charged,Pen) :-
       bag(BagId,L,W,H,Wt),
       dims_sum(L,W,H,S),
       oversize_fee(S,OS),
       overweight_fee(Wt,50,OW),           % charged-bag threshold
       Pen is max(OS,OW).

/* base checked-bag fee for Business Class on this route              */
bag_fee(1,0).          % 1st bag - free
bag_fee(2,0).          % 2nd bag - free
bag_fee(3,150).        % 3rd bag
bag_fee(N,200) :- N>=4.% 4th bag and beyond


/* -------------  Minimisation routine ------------------------------ */

/* choose two different elements (F1 < F2) from a list                */
choose_two(List,F1,F2) :-
       append(_,[F1|Tail],List),
       member(F2,Tail).

/* place the 2 freebies first, keep remaining order for the rest      */
ordered_list(F1,F2,Ordered) :-
       checked_bag_ids(All),
       select(F1,All,R1),
       select(F2,R1,Rest),
       Ordered = [F1,F2|Rest].

/* cost for a particular choice of the 2 complimentary bags           */
cost_for_choice(F1,F2,Total) :-
       ordered_list(F1,F2,Ordered),
       cost_bags(Ordered,1,BagsCost,PenCost),
       flight_cost(Tix),
       Total is Tix + BagsCost + PenCost.

/* walk the ordered list calculating cumulative costs                 */
cost_bags([],_,0,0).
cost_bags([Bag|Bs],Idx,Csum,Psum) :-
       (Idx =< 2 -> Kind = comp ; Kind = charged),
       bag_fee(Idx,BaseFee),
       penalty(Bag,Kind,Pen),
       Next is Idx + 1,
       cost_bags(Bs,Next,Crest,Prest),
       Csum is BaseFee + Crest,
       Psum is Pen + Prest.

/* minimal total over all possible ways to pick the 2 freebies        */
total_cost(MinTotal) :-
       checked_bag_ids(L),
       findall(T,
               ( choose_two(L,F1,F2),
                 cost_for_choice(F1,F2,T)),
               Totals),
       min_list(Totals,MinTotal).


/* -------------  Final query / output ------------------------------ */
:- total_cost(Total), format('Total cost: ~w~n', [Total]).
:- halt.