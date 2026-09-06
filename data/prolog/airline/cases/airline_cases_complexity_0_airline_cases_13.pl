:- format("~w~n", ["Label: 992"]).
/* =========================================================
   Michael - Business Class
   Toronto (Canada)  ->  Philadelphia (U.S.)
   Route category: Within / between U.S. and Canada
   ========================================================= */

/* ---------------  Ticket price  ------------------------- */
flight_cost(352).

/* ---------------  Carry-on item (free) ------------------ */
/* Bag #1 (21*14*7, 10 lbs) fits the carry-on limits, so it
   is NOT included in the checked-bag list.                 */

/* ---------------  Checked bags  ------------------------- */
/* bag(Id,Length,Width,Height,Weight)                      */
bag(2,34,20,11,51).
bag(3,48,36,24,51).
bag(4,34,21, 9,68).
bag(5,35,14,14,52).

/* list of all checked-bag Ids (in no particular order)    */
checked_bag_ids([2,3,4,5]).

/* ---------------  Statutory rules  ---------------------- */

/* total (L+W+H) */
dims_sum(L,W,H,S) :- S is L+W+H.

/* Oversize fees - within / between U.S. & Canada */
oversize_fee(Sum,Fee) :-
        (  Sum =< 62  -> Fee = 0
        ;  Sum =< 65  -> Fee = 30
        ;  Sum =< 115 -> Fee = 200).

/* Overweight fees - threshold depends on whether
   the bag's BASE fee is complimentary (70 lbs) or charged (50 lbs). */
overweight_fee(Weight,Thresh,Fee) :-
        (  Weight =< Thresh -> Fee = 0
        ;  Weight =< 53     -> Fee = 30
        ;  Weight =< 70     -> Fee = 100
        ;  Weight =< 100    -> Fee = 200).

/* Penalty = higher of the oversize vs. overweight fee */
penalty(BagId,comp,Pen) :-           % complimentary bag
        bag(BagId,L,W,H,Wt),
        dims_sum(L,W,H,S),
        oversize_fee(S,OS),
        overweight_fee(Wt,70,OW),
        Pen is max(OS,OW).

penalty(BagId,charged,Pen) :-        % charged bag
        bag(BagId,L,W,H,Wt),
        dims_sum(L,W,H,S),
        oversize_fee(S,OS),
        overweight_fee(Wt,50,OW),
        Pen is max(OS,OW).

/* Base checked-bag fees for Business Class on this route */
bag_fee(1,0).
bag_fee(2,0).
bag_fee(3,150).
bag_fee(N,200) :- N >= 4.

/* ---------------  Helper predicates  -------------------- */

/* choose two different elements (F1 < F2) from a list */
choose_two(List,F1,F2) :-
        append(_,[F1|Tail],List),
        member(F2,Tail).

/* build the ordered list of bags: freebies first          */
ordered_list(F1,F2,Ordered) :-
        checked_bag_ids(All),
        select(F1,All,R1),
        select(F2,R1,R2),
        Ordered = [F1,F2|R2].

/* cost for one concrete choice of the 2 complimentary bags */
cost_for_choice(F1,F2,Total) :-
        ordered_list(F1,F2,Ordered),
        cost_bags(Ordered,1,BagCost,Penalties),
        flight_cost(Tix),
        Total is Tix + BagCost + Penalties.

/* walk through the ordered list accumulating base fees
   (BagCost) and penalties (Penalties)                     */
cost_bags([],_,0,0).
cost_bags([Bag|Bs],Idx,BagSum,PenSum) :-
        (Idx =< 2 -> Type = comp ; Type = charged),
        bag_fee(Idx,Base),
        penalty(Bag,Type,Pen),
        Next is Idx+1,
        cost_bags(Bs,Next,BagRest,PenRest),
        BagSum is Base + BagRest,
        PenSum  is Pen + PenRest.

/* ---------------  Overall minimal total cost ------------ */
total_cost(MinTotal) :-
        checked_bag_ids(List),
        findall(T,
                ( choose_two(List,F1,F2),
                  cost_for_choice(F1,F2,T)),
                Totals),
        min_list(Totals,MinTotal).

/* ---------------  Query & result ------------------------ */
:- total_cost(Total), format('Total cost: ~w~n', [Total]).
:- halt.