/* ================================================================
   William - Business Class
   New Orleans (MSY)  ->  Boston (BOS)
   Statutory luggage calculator
   ================================================================ */

               /* ----------  Ticket ------------------------------ */

flight_cost(269).


               /* ----------  Bags -------------------------------- */
/* Id, Length, Width, Height, Weight (lbs) - *checked* bags only   */
bag(2,50,37,27,75).
bag(3,37,15,13,58).
bag(4,46,26,23,87).
bag(5,36,19, 9,72).
bag(6,41,28,20,54).
bag(7,38,26,14,79).
bag(8,48,28,24,52).

/* list of all checked-bag Ids in the order they're presented      */
checked_bag_ids([2,3,4,5,6,7,8]).

               /* ----------  Statutory rules --------------------- */

/* sum of outside dimensions */
dims_sum(L,W,H,S) :- S is L+W+H.

/* oversize fee - travel within / between U.S. and Canada          */
oversize_fee(S,Fee) :-
        (  S =< 62     -> Fee = 0
        ;  S =< 65     -> Fee = 30
        ;  S =< 115    -> Fee = 200 ).

/* overweight fee - 'Thresh' is 70 lb for complimentary bags,
   50 lb for charged bags                                          */
overweight_fee(W,Thresh,Fee) :-
        (  W =< Thresh -> Fee = 0
        ;  W =< 53     -> Fee = 30
        ;  W =< 70     -> Fee = 100
        ;  W =< 100    -> Fee = 200 ).

/* penalty = higher of oversize vs overweight                     */
penalty(B,comp,Pen) :-
        bag(B,L,W,H,WT),
        dims_sum(L,W,H,S),
        oversize_fee(S,OS),
        overweight_fee(WT,70,OW),
        Pen is max(OS,OW).

penalty(B,charged,Pen) :-
        bag(B,L,W,H,WT),
        dims_sum(L,W,H,S),
        oversize_fee(S,OS),
        overweight_fee(WT,50,OW),
        Pen is max(OS,OW).

/* checked-bag base fees - Business Class, domestic                */
bag_fee(1,0).     /* 1st complimentary */
bag_fee(2,0).     /* 2nd complimentary */
bag_fee(3,150).   /* 3rd bag           */
bag_fee(N,200) :- N >= 4.   /* 4th +  */


/* ----------  Helper predicates --------------------------------- */

/* choose any 2 distinct elements (F1 < F2) from a list            */
choose_two(List,F1,F2) :-
        append(_,[F1|Tail],List),
        member(F2,Tail).

/* place the 2 chosen freebies in positions 1 and 2                */
ordered_list(F1,F2,Ordered) :-
        checked_bag_ids(All),
        select(F1,All,R1),
        select(F2,R1,Rest),
        Ordered = [F1,F2|Rest].

/* accumulate costs for a particular ordering                      */
cost_bags([],_,0,0).
cost_bags([Bag|Bs],Idx,FeeSum,PenSum) :-
        (Idx =< 2 -> Type = comp ; Type = charged),
        bag_fee(Idx,Fee),
        penalty(Bag,Type,Pen),
        Next is Idx + 1,
        cost_bags(Bs,Next,FeeRest,PenRest),
        FeeSum is Fee + FeeRest,
        PenSum  is Pen + PenRest.

/* total cost for one choice of complimentary bags                 */
cost_for_choice(F1,F2,Total) :-
        ordered_list(F1,F2,Ordered),
        cost_bags(Ordered,1,BaseFees,Penalties),
        flight_cost(Flight),
        Total is Flight + BaseFees + Penalties.

/* compute minimal total over all ways of picking the 2 freebies   */
total_cost(Min) :-
        checked_bag_ids(L),
        findall(T,
                (choose_two(L,F1,F2),
                 cost_for_choice(F1,F2,T)),
                Totals),
        min_list(Totals,Min).

/* ----------  Query & output ------------------------------------ */
:- total_cost(Total), format('Total cost: ~w~n', [Total]).
:- halt.