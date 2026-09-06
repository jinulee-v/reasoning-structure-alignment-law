/* ------------  Facts describing Emily's trip ------------------- */

/* ticket price */
flight_cost(435).

/* checked bags:  bag(Id,Length,Width,Height,Weight)               */
bag(2,47,26,18,52).
bag(3,49,29,23,51).
bag(4,40,23,20,57).
bag(5,36,13,14,53).
bag(6,42,17,19,68).
bag(7,37,17, 9,64).
bag(8,37,15,13,65).
bag(9,34,18,12,62).
bag(10,33,19,12,54).
bag(11,33,19,12,51).

/* list of all checked-bag Ids (carry-on item #1 is excluded)      */
checked_bag_ids([2,3,4,5,6,7,8,9,10,11]).

/* itinerary type */
itinerary(europe_us).

/* ------------  Statutory rules for this itinerary --------------- */

/* sum of the 3 dimensions */
dims_sum(L,W,H,S) :- S is L+W+H.

/* oversize fee - Europe  <->  U.S.                                  */
oversize_fee(Sum,Fee) :-
        (   Sum =< 62  -> Fee = 0
        ;   Sum =< 65  -> Fee = 30
        ;   Sum =< 115 -> Fee = 150 ).

/* overweight fee - 'Limit' is 70 lb for complimentary bags,
   50 lb for charged bags (statutory distinction)                  */
overweight_fee(W,Limit,Fee) :-
        (   W =< Limit -> Fee = 0
        ;   W =< 53    -> Fee = 30
        ;   W =< 70    -> Fee = 100
        ;   W =< 100   -> Fee = 200 ).

/* penalty = higher of oversize vs. overweight                     */
penalty(BagId,complimentary,Pen) :-
        bag(BagId,L,W,H,Wt),
        dims_sum(L,W,H,S),
        oversize_fee(S,OS),
        overweight_fee(Wt,70,OW),
        Pen is max(OS,OW).

penalty(BagId,charged,Pen) :-
        bag(BagId,L,W,H,Wt),
        dims_sum(L,W,H,S),
        oversize_fee(S,OS),
        overweight_fee(Wt,50,OW),
        Pen is max(OS,OW).

/* checked-bag base fee - First Class, Europe <-> U.S.               */
bag_fee(N,0)   :- N>=1, N=<3.          /* first 3 bags free */
bag_fee(N,200) :- N=4.                 /* 4th bag */
bag_fee(N,200) :- N=5.                 /* 5th bag */
bag_fee(N,200) :- N=6.                 /* 6th bag */
bag_fee(N,200) :- N=7.                 /* 7th bag */
bag_fee(N,200) :- N=8.                 /* 8th bag */
bag_fee(N,200) :- N=9.                 /* 9th bag */
bag_fee(N,200) :- N=10.                /* 10th bag */

/* ------------  Helper predicates --------------------------------*/

/* pick 3 different list elements (A<B<C in the list order)        */
choose_three(List,A,B,C) :-
        append(_, [A|T1], List),
        append(_, [B|T2], T1),
        member(C, T2).

/* build ordered list: complimentary bags occupy positions 1-3     */
ordered_list(A,B,C,Ordered) :-
        checked_bag_ids(All),
        select(A,All,R1),
        select(B,R1,R2),
        select(C,R2,Rest),
        Ordered = [A,B,C | Rest].

/* walk the ordered list and total up base fees + penalties        */
cost_bags([],_,0,0).
cost_bags([Bag|Bs],Idx,FeeSum,PenSum) :-
        (Idx =< 3 -> Kind = complimentary ; Kind = charged),
        bag_fee(Idx,Fee),
        penalty(Bag,Kind,Pen),
        Next is Idx+1,
        cost_bags(Bs,Next,FRest,PRest),
        FeeSum is Fee + FRest,
        PenSum is Pen + PRest.

/* compute total for one particular choice of 3 free bags          */
cost_for_choice(A,B,C,Total) :-
        ordered_list(A,B,C,Ordered),
        cost_bags(Ordered,1,Fees,Penalties),
        flight_cost(T),
        Total is T + Fees + Penalties.

/* minimal total over all ways of choosing 3 complimentary bags    */
compute_total(Min) :-
        checked_bag_ids(List),
        findall(T,
                ( choose_three(List,A,B,C),
                  cost_for_choice(A,B,C,T) ),
                Totals),
        min_list(Totals,Min).

/* ------------  Query and formatted output -----------------------*/
:- compute_total(Cost), format('Total cost: ~w~n', [Cost]), halt.