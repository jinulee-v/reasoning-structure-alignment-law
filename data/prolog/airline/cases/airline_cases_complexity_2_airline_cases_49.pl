/* =================================================================
   American Airlines - baggage charges
   Case:  Jennifer - Chicago (U.S.)  ->  Helsinki (Finland)
          First Class
          Ticket price  : $204
   ================================================================= */

/* --------------- facts describing the itinerary ---------------- */

flight_cost(204).                       /* ticket price           */
cabin(first).                           /* First Class            */
route(us_europe).                       /* U.S.  <->  Europe route  */

/* list of checked bags:  bag(Id,Length,Width,Height,Weight).      */
/* (Bag 1 is the carry-on and is therefore not listed here.)       */
bag(2, 37,18,17,64).
bag(3, 33,20,12,53).
bag(4, 52,28,29,52).
bag(5, 36,20, 9,52).
bag(6, 51,33,24,62).
bag(7, 50,31,30,52).
bag(8, 34,16,13,58).
bag(9, 52,36,27,52).
bag(10,36,17,12,61).
bag(11,33,21, 9,69).

/* a fixed list of all checked-bag Ids (convenience)              */
checked_bag_ids([2,3,4,5,6,7,8,9,10,11]).

/* --------------- statutory rules (U.S. <-> Europe) --------------- */

/* sum of the 3 external dimensions of a bag */
dims_sum(L,W,H,S) :- S is L+W+H.


/* ---------------------------------------------------------------
   Over-SIZE fees - U.S. / Europe                                  */
/* ( 0 - 62 in )          : $0                                     */
/* (62 - 65 in]           : $30                                    */
/* (65 - 115 in]          : $150                                   */
oversize_fee(Sum,Fee) :-
        (  Sum =< 62   -> Fee = 0
        ;  Sum =< 65   -> Fee = 30
        ;  Sum =< 115  -> Fee = 150
        ).

/* ---------------------------------------------------------------
   Over-WEIGHT fees - U.S. / Europe                                */
/* For CHARGED bags the free limit is 50 lb.                       */
/* For COMPLIMENTARY bags the free limit is 70 lb.                 */
/* The statutory bands are:                                        */
/*   (50 - 53]  -> $30   (only relevant for charged bags)          */
/*   (53 - 70]  -> $100  (for either kind if above free limit)     */
/*   (>70)      -> $200  (fees shown here; in practice >70 not
                          accepted on this route, but we follow
                          the template of Example 2)               */
overweight_fee(W,FreeLimit,Fee) :-
        ( W =< FreeLimit -> Fee = 0
        ; W =< 53        -> Fee = 30
        ; W =< 70        -> Fee = 100
        ; W =< 100       -> Fee = 200
        ).

/* ---------------------------------------------------------------
   Penalty for a bag = max(oversize fee, overweight fee)           */
/* Two variants:  'comp' for complimentary bags (70-lb limit)      */
/*                'charged' for paid bags      (50-lb limit)       */
penalty(BagId,comp,Pen) :-
        bag(BagId,L,W,H,Weight),
        dims_sum(L,W,H,Sum),
        oversize_fee(Sum,OS),
        overweight_fee(Weight,70,OW),        % 70-lb allowance
        Pen is max(OS,OW).

penalty(BagId,charged,Pen) :-
        bag(BagId,L,W,H,Weight),
        dims_sum(L,W,H,Sum),
        oversize_fee(Sum,OS),
        overweight_fee(Weight,50,OW),        % 50-lb allowance
        Pen is max(OS,OW).


/* --------------- checked-bag base fee by ordinal position ------ */
/* First Class - U.S. <-> Europe                                     */
bag_fee(Pos,0)  :- Pos =< 3.     /* 1st-3rd bags are free          */
bag_fee(Pos,200) :- Pos >= 4.    /* 4th bag and beyond             */


/* --------------- helper predicates ----------------------------- */

/* choose three different elements (F1<F2<F3) from a list */
choose_three(List,F1,F2,F3) :-
        append(_,[F1|Rest1],List),
        append(_,[F2|Rest2],Rest1),
        member(F3,Rest2).

/* construct an ordered list: freebies go first                    */
ordered_list(F1,F2,F3,Ordered) :-
        checked_bag_ids(All),
        select(F1,All,R1),
        select(F2,R1,R2),
        select(F3,R2,Remainder),
        Ordered = [F1,F2,F3 | Remainder].

/* cost for a specific choice of the 3 complimentary bags          */
cost_for_choice(F1,F2,F3,Total) :-
        ordered_list(F1,F2,F3,Ordered),
        cost_bags(Ordered,1,BaseFees,Penalties),
        flight_cost(Flight),
        Total is Flight + BaseFees + Penalties.

/* walk through ordered list, accumulating base fees & penalties   */
cost_bags([],_,0,0).
cost_bags([Bag|Bs],Idx,BaseSum,PenSum) :-
        (Idx =< 3 -> Kind = comp ; Kind = charged),
        bag_fee(Idx,Fee),
        penalty(Bag,Kind,Pen),
        NextIdx is Idx + 1,
        cost_bags(Bs,NextIdx,BaseRest,PenRest),
        BaseSum is Fee + BaseRest,
        PenSum  is Pen + PenRest.

/* compute the minimal total cost over all ways of selecting
   which 3 bags are complimentary                                   */
total_cost(MinTotal) :-
        checked_bag_ids(L),
        findall(T,
                ( choose_three(L,F1,F2,F3),
                  cost_for_choice(F1,F2,F3,T)
                ),
                Totals),
        min_list(Totals,MinTotal).


/* --------------- query & formatted output ---------------------- */
:- total_cost(Total), format('Total cost: ~w~n',[Total]).
:- halt.