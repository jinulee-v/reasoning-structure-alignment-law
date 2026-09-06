:- format("~w~n", ["Label: 3695"]).
/*  Emily - Premium Economy - San Francisco (U.S.)  ->  Auckland (New Zealand)  */

/*  Base ticket price  */
flight_cost(875).


/*  Checked bags: bag(Id,Length,Width,Height,Weight)  */
bag(2,44,29,20,62).
bag(3,45,23,19,53).
bag(4,36,18, 9,66).
bag(5,33,21,10,53).
bag(6,46,31,27,57).
bag(7,36,15,14,63).
bag(8,35,18,10,58).
bag(9,51,29,24,52).
bag(10,37,17, 9,52).
bag(11,38,20,13,53).

/*  List of all checked-bag Ids  */
checked_bag_ids([2,3,4,5,6,7,8,9,10,11]).

/* -----------------------------------------------------------
   Statutory rules applicable to the itinerary
   ----------------------------------------------------------- */

/*  Sum of the 3 dimensions  */
dims_sum(L,W,H,S) :- S is L+W+H.

/*  Oversize fee for travel to / from Australia / New Zealand  */
oversize_fee(Sum,Fee) :-
        (   Sum =< 62  -> Fee = 0
        ;   Sum =< 65  -> Fee = 30
        ;   Sum =< 115 -> Fee = 200 ).

/*  Over-weight fee
       Thresh = max weight allowed at no charge
       (70 lb for complimentary bags, 50 lb for charged bags)            */
overweight_fee(W,Thresh,Fee) :-
        (   W =< Thresh -> Fee = 0
        ;   W =< 53     -> Fee = 30
        ;   W =< 70     -> Fee = 100
        ;   W =< 100    -> Fee = 200 ).

/*  Penalty is the higher of over-size vs over-weight  */
penalty(BagId,comp,Pen) :-
        bag(BagId,L,W,H,Weight),
        dims_sum(L,W,H,Sum),
        oversize_fee(Sum,OS),
        overweight_fee(Weight,70,OW),      % complimentary bag -> 70-lb limit
        Pen is max(OS,OW).

penalty(BagId,charged,Pen) :-
        bag(BagId,L,W,H,Weight),
        dims_sum(L,W,H,Sum),
        oversize_fee(Sum,OS),
        overweight_fee(Weight,50,OW),      % charged bag -> 50-lb limit
        Pen is max(OS,OW).

/*  Checked-bag base fee schedule - Premium Economy (U.S.-NZ)  */
bag_fee(1,0).
bag_fee(2,0).
bag_fee(N,200) :- N >= 3.

/* -----------------------------------------------------------
   Helper predicates
   ----------------------------------------------------------- */

/*  Choose two different elements (F1<F2) from a list  */
choose_two(List,F1,F2) :-
        append(_, [F1|Tail], List),
        member(F2, Tail).

/*  Put the two complimentary bags first in the ordered list  */
ordered_list(F1,F2,Ordered) :-
        checked_bag_ids(All),
        select(F1,All,Rest1),
        select(F2,Rest1,Rest),
        Ordered = [F1,F2|Rest].

/*  Cost for a specific choice of complimentary bags  */
cost_for_choice(F1,F2,Total) :-
        ordered_list(F1,F2,Ordered),
        cost_bags(Ordered,1,BagFees,Penalties),
        flight_cost(Flight),
        Total is Flight + BagFees + Penalties.

/*  Walk the ordered list accumulating fees and penalties  */
cost_bags([],_,0,0).
cost_bags([Bag|Bs],Idx,CostSum,PenSum) :-
        (Idx =< 2 -> Type = comp ; Type = charged),
        bag_fee(Idx,Fee),
        penalty(Bag,Type,Pen),
        NextIdx is Idx + 1,
        cost_bags(Bs,NextIdx,CostRest,PenRest),
        CostSum is Fee + CostRest,
        PenSum  is Pen + PenRest.

/*  Minimal total cost over all ways of picking 2 complimentary bags  */
total_cost(MinTotal) :-
        checked_bag_ids(L),
        findall(T,
                ( choose_two(L,F1,F2),
                  cost_for_choice(F1,F2,T) ),
                Totals),
        min_list(Totals,MinTotal).

/* -----------------------------------------------------------
   Query and output
   ----------------------------------------------------------- */
:- total_cost(Total), format('Total cost: ~w~n', [Total]).
:- halt.