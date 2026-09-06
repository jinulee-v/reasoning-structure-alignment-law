:- format("~w~n", ["Label: 1349"]).
/* ===================================================================
   John - Las Vegas (U.S.)  ->  Amsterdam (Europe)
   Cabin: Business
   Goal : compute grand-total (ticket + all luggage charges)
   =================================================================== */

:- use_module(library(lists)).

/* ----------  Ticket  ---------- */
flight_cost(589).

/* ----------  Items brought  --------------------------------------- */
/* bag(Id,Length,Width,Height,Weight).  (dimensions in inches, weight in lbs) */
bag(1,18,13, 6,  7).   /* fits carry-on limits -> free                     */
bag(2,36,18, 9, 53).
bag(3,43,31,21, 52).
bag(4,47,23,23, 51).
bag(5,37,14,12, 57).

/* ----------  Carry-on rules --------------------------------------- */
carry_on_max(22,14,9).

carry_on(Id) :-
        bag(Id,L,W,H,_),
        carry_on_max(MaxL,MaxW,MaxH),
        L =< MaxL, W =< MaxW, H =< MaxH.

/* ----------  Helper: list of checked bags ------------------------- */
checked_bag_ids(List) :-
        findall(Id,(bag(Id,_,_,_,_), \+ carry_on(Id)),List).
/* For John: List = [2,3,4,5]                                         */

/* ----------  Geometry & Weight helpers ---------------------------- */
dims_sum(L,W,H,S) :- S is L+W+H.

/* ----------  Oversize fees (U.S. <-> Europe) ------------------------ */
/* 62 in or less  -> $0
   62-65 in       -> $30
   65-115 in      -> $150                                              */
oversize_fee(Sum,Fee) :-
        (  Sum =< 62  -> Fee = 0
        ;  Sum =< 65  -> Fee = 30
        ;  Sum =< 115 -> Fee = 150).

/* ----------  Overweight fees (U.S. <-> Europe) ---------------------- */
/* 'Thresh' is the free allowance (70 lb for complimentary bags,
                                    50 lb for charged bags)          */
overweight_fee(W,Thresh,Fee) :-
        (  W =< Thresh -> Fee = 0
        ;  W =< 53     -> Fee = 30
        ;  W =< 70     -> Fee = 100
        ;               fail                 /* >70 lb not accepted  */
        ).

/* ----------  Penalty = higher of oversize / overweight ------------ */
penalty(Id,comp,Pen) :-
        bag(Id,L,W,H,Weight),
        dims_sum(L,W,H,Sum),
        oversize_fee(Sum,OS),
        overweight_fee(Weight,70,OW),
        Pen is max(OS,OW).

penalty(Id,charged,Pen) :-
        bag(Id,L,W,H,Weight),
        dims_sum(L,W,H,Sum),
        oversize_fee(Sum,OS),
        overweight_fee(Weight,50,OW),
        Pen is max(OS,OW).

/* ----------  Base checked-bag fees for Business (U.S.-Europe) ----- */
/* 1st & 2nd bag free, 3rd bag $200, 4th+ $200                        */
bag_fee(1,0).
bag_fee(2,0).
bag_fee(3,200).
bag_fee(N,200) :- N >= 4.

/* ----------  Choose which 2 bags receive the complimentary spots -- */
choose_two(List,B1,B2) :-
        append(_, [B1|Tail], List),
        member(B2, Tail).

ordered_list(B1,B2,Ordered) :-
        checked_bag_ids(All),
        select(B1,All,R1),
        select(B2,R1,R2),
        Ordered = [B1,B2|R2].   /* freebies occupy positions 1 & 2 */

/* ----------  Cost for a particular choice of freebies ------------- */
cost_for_choice(B1,B2,Total) :-
        ordered_list(B1,B2,Ordered),
        cost_bags(Ordered,1,CostBags,Penalties),
        flight_cost(Ticket),
        Total is Ticket + CostBags + Penalties.

/* Walk through list, accumulating base fees and penalties            */
cost_bags([],_,0,0).
cost_bags([Bag|Bs],Idx,CostSum,PenSum) :-
        (Idx =< 2 -> Kind = comp ; Kind = charged),
        bag_fee(Idx,BaseFee),
        penalty(Bag,Kind,Pen),
        Next is Idx + 1,
        cost_bags(Bs,Next,CostRest,PenRest),
        CostSum is BaseFee + CostRest,
        PenSum  is Pen      + PenRest.

/* ----------  Compute minimal total over all choices --------------- */
total_cost(MinTotal) :-
        checked_bag_ids(L),
        findall(T, (choose_two(L,B1,B2),
                    cost_for_choice(B1,B2,T)),
                Totals),
        min_list(Totals,MinTotal).

/* ----------  Query & output --------------------------------------- */
:- total_cost(Total), format('Total cost: ~w~n',[Total]).
:- halt.