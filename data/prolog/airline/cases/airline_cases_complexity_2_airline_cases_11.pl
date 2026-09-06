/* ----------------------------------------------------------
   Facts describing Charles' trip
   ---------------------------------------------------------- */

/* ticket price */
flight_cost(516).

/* carry-on bag (free) - not listed among checked bags */
carry_on(1).

/* checked bags : bag(Id,Length,Width,Height,Weight) */
bag(2,47,29,24,51).
bag(3,45,20,22,51).
bag(4,37,18,10,60).
bag(5,39,25,18,59).
bag(6,37,13,14,56).
bag(7,45,27,23,53).
bag(8,45,23,16,63).
bag(9,37,15,12,61).
bag(10,44,20,18,57).
bag(11,36,19,17,55).

/* list of all checked-bag Ids (in their given order) */
checked_bag_ids([2,3,4,5,6,7,8,9,10,11]).

/* ----------------------------------------------------------
   Statutory rules for a First-Class itinerary
   between Europe and the U.S.
   ---------------------------------------------------------- */

/* sum of the 3 dimensions */
dims_sum(L,W,H,S) :- S is L+W+H.

/* oversize fees (Europe <--> U.S.) */
oversize_fee(Sum,Fee) :-
        (   Sum =< 62      -> Fee = 0
        ;   Sum =< 65      -> Fee = 30
        ;   Sum =< 115     -> Fee = 150 ).

/* overweight fees - 'Thresh' is 70 lb for complimentary bags,
   50 lb for charged bags                                       */
overweight_fee(W,Thresh,Fee) :-
        (   W =< Thresh    -> Fee = 0
        ;   W =< 53        -> Fee = 30
        ;   W =< 70        -> Fee = 100
        ;   W =< 100       -> Fee = 200 ).

/* penalty for a bag = max(oversize , overweight) */
penalty(BagId,comp,Pen) :-
        bag(BagId,L,W,H,Weight),
        dims_sum(L,W,H,Sum),
        oversize_fee(Sum,OS),
        overweight_fee(Weight,70,OW),
        Pen is max(OS,OW).

penalty(BagId,charged,Pen) :-
        bag(BagId,L,W,H,Weight),
        dims_sum(L,W,H,Sum),
        oversize_fee(Sum,OS),
        overweight_fee(Weight,50,OW),
        Pen is max(OS,OW).

/* checked-bag base fee for First Class, Europe <-> U.S.
   (1st-3rd free, 4th+ = $200)                                   */
bag_fee(Idx,0)   :- Idx =< 3.
bag_fee(Idx,200) :- Idx  > 3.

/* ----------------------------------------------------------
   Helper predicates
   ---------------------------------------------------------- */

/* choose three different elements (A < B < C) out of a list */
choose_three(List,A,B,C) :-
        append(_, [A|Tail1], List),
        append(_, [B|Tail2], Tail1),
        member(C, Tail2).

/* build the ordered list putting the 3 complimentary bags first */
ordered_list(A,B,C,Ordered) :-
        checked_bag_ids(All),
        select(A,All,R1),
        select(B,R1,R2),
        select(C,R2,R3),
        Ordered = [A,B,C|R3].

/* cost for ONE particular choice of complimentary bags */
cost_for_choice(A,B,C,Total) :-
        ordered_list(A,B,C,Ordered),
        cost_bags(Ordered,1,BagsCost,Penalties),
        flight_cost(Fare),
        Total is Fare + BagsCost + Penalties.

/* walk through the ordered checked-bag list,
   accumulating base fees and penalties                    */
cost_bags([],_,0,0).
cost_bags([Bag|Bs],Idx,CostSum,PenSum) :-
        (Idx =< 3 -> Type = comp ; Type = charged),
        bag_fee(Idx,BaseFee),
        penalty(Bag,Type,Pen),
        Next is Idx+1,
        cost_bags(Bs,Next,RestCost,RestPen),
        CostSum is BaseFee + RestCost,
        PenSum  is Pen + RestPen.

/* ----------------------------------------------------------
   Grand-total: minimise over all ways of selecting 3 freebies
   ---------------------------------------------------------- */
total_cost(MinTotal) :-
        checked_bag_ids(List),
        findall(T,
                ( choose_three(List,A,B,C),
                  cost_for_choice(A,B,C,T) ),
                Totals),
        min_list(Totals,MinTotal).

/* ----------------------------------------------------------
   Query and output
   ---------------------------------------------------------- */
:- total_cost(Total), format('Total cost: ~w~n',[Total]).
:- halt.