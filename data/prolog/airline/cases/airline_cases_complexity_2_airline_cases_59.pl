:- format("~w~n", ["Label: 2603"]).
/* ========================================================================
   Patricia - First Class   -  Las Vegas  (U.S.)  ->  London  (Europe)
   Statutory baggage rules: U.S. <-> Europe
   ======================================================================== */

/* ----------  Ticket price  -------------------------------------------- */
flight_cost(353).


/* ----------  Bags to be checked --------------------------------------- */
/*    bag(Id, Length, Width, Height, Weight).  */
bag(2,33,18,14,58).
bag(3,45,32,20,69).
bag(4,33,23, 9,58).
bag(5,54,32,25,54).
bag(6,52,35,27,62).
bag(7,33,22, 9,69).
bag(8,34,18,11,53).
bag(9,33,17,14,67).
bag(10,34,19,11,52).
bag(11,40,15,15,52).

/* carry-on (Id 1) fits the 22*14*9 limit, so it isn't listed here        */
checked_bag_ids([2,3,4,5,6,7,8,9,10,11]).

/* ----------  Statutory fees  ------------------------------------------ */

/* Sum of dimensions */
dims_sum(L,W,H,S) :- S is L+W+H.

/* Oversize - Between U.S. and Europe */
oversize_fee(Sum,Fee) :-
       (   Sum =< 62      -> Fee = 0
       ;   Sum =< 65      -> Fee = 30
       ;   Sum =< 115     -> Fee = 150 ).

/* Overweight - Between U.S. and Europe
   Thresh = allowed-weight limit for the bag type (70 lbs comp / 50 lbs charged) */
overweight_fee(W,Thresh,Fee) :-
       (   W =< Thresh        -> Fee = 0
       ;   W =< 53            -> Fee = 30
       ;   W =< 70            -> Fee = 100
       ;   W =< 100           -> fail ).           % >70 lbs not accepted on this route

/* Penalty = higher of oversize vs overweight                                */
penalty(BagId,comp,Pen) :-
       bag(BagId,L,W,H,Weight),
       dims_sum(L,W,H,S),
       oversize_fee(S,OS),
       overweight_fee(Weight,70,OW),
       Pen is max(OS,OW).

penalty(BagId,charged,Pen) :-
       bag(BagId,L,W,H,Weight),
       dims_sum(L,W,H,S),
       oversize_fee(S,OS),
       overweight_fee(Weight,50,OW),
       Pen is max(OS,OW).

/* Checked-bag base fee for First Class - U.S. <-> Europe                      */
bag_fee(Idx,0)   :- Idx =< 3.        /* 1st-3rd bags complimentary */
bag_fee(Idx,200) :- Idx  >= 4.       /* 4th bag and beyond         */

/* ----------  Helper predicates ---------------------------------------- */

/* Choose three distinct elements (F1<F2<F3) from a list                    */
choose_three(List,F1,F2,F3) :-
       append(_, [F1|T1], List),
       append(_, [F2|T2], T1), F1 @< F2,
       append(_, [F3|_ ], T2), F2 @< F3.

/* Place the freebies in positions 1-3, keep remaining order thereafter     */
ordered_list(F1,F2,F3,Ordered) :-
       checked_bag_ids(All),
       select(F1,All,R1),
       select(F2,R1,R2),
       select(F3,R2,Rest),
       Ordered = [F1,F2,F3|Rest].

/* Walk the ordered list, accumulating base fees and penalties              */
cost_bags([],_,0).
cost_bags([Bag|Bs],Idx,Total) :-
       (Idx =< 3 -> Kind = comp ; Kind = charged),
       bag_fee(Idx,Base),
       penalty(Bag,Kind,Pen),
       Next is Idx+1,
       cost_bags(Bs,Next,Rest),
       Total is Base + Pen + Rest.

/* Cost for a specific choice of the 3 complimentary bags                   */
cost_for_choice(F1,F2,F3,Total) :-
       ordered_list(F1,F2,F3,Ordered),
       cost_bags(Ordered,1,BagCost),
       flight_cost(Tix),
       Total is Tix + BagCost.

/* Minimum total over all ways to choose the 3 complimentary bags            */
total_cost(Min) :-
       checked_bag_ids(L),
       findall(T,
               ( choose_three(L,F1,F2,F3),
                 cost_for_choice(F1,F2,F3,T) ),
               Totals),
       min_list(Totals,Min).


/* ----------  Query & output -------------------------------------------- */
:- total_cost(Total), format('Total cost: ~w~n', [Total]).
:- halt.