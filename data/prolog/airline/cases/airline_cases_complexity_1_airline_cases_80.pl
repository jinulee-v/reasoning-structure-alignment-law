:- format("~w~n", ["Label: 2798"]).
/* =========================================================
   Joseph - Auckland (NZ)  ->  San Francisco (U.S.)
   Business Class
   Goal: compute total trip cost (ticket + all bag charges)
   ========================================================= */

/* ----------  Flight ticket  ----------------------------- */
flight_cost(908).

/* ----------  Checked bags  ------------------------------ */
/*   bag(Id, Length, Width, Height, Weight).               */
bag(2,46,23,18,69).
bag(3,42,23,18,70).
bag(4,39,17,14,53).
bag(5,34,20,10,51).
bag(6,41,26,20,57).
bag(7,37,13,14,60).
bag(8,35,16,13,53).

/* list of all checked-bag Ids, in original order           */
checked_bag_ids([2,3,4,5,6,7,8]).

/* ----------  Statutory charges for this itinerary  ------ */

/* (1) Base checked-bag fees: Business Class, to / from
      Australia or New Zealand                               */
bag_fee(1,0).               /* 1st bag complimentary  */
bag_fee(2,0).               /* 2nd bag complimentary  */
bag_fee(N,200) :- N>=3.     /* 3rd + bags             */

/* (2) Oversize fees: Australia / New Zealand region        */
oversize_fee(Sum,Fee) :-
        (  Sum =< 62      -> Fee = 0
        ;  Sum =< 65      -> Fee = 30
        ;  Sum =< 115     -> Fee = 200 ).

/* (3) Overweight fees                                       */
/*     - complimentary bags: 70-lb allowance
       - charged   bags: 50-lb allowance                     */
overweight_fee(W,Allow,Fee) :-
        (  W =< Allow     -> Fee = 0
        ;  W =< 53        -> Fee = 30
        ;  W =< 70        -> Fee = 100
        ;  W =< 100       -> Fee = 200 ).

/* (4) Penalty for one bag = higher of oversize vs overweight*/
penalty(BagId,comp,Pen) :-
        bag(BagId,L,W,H,Wt),
        Sum is L+W+H,
        oversize_fee(Sum,OS),
        overweight_fee(Wt,70,OW),
        Pen is max(OS,OW).

penalty(BagId,charged,Pen) :-
        bag(BagId,L,W,H,Wt),
        Sum is L+W+H,
        oversize_fee(Sum,OS),
        overweight_fee(Wt,50,OW),
        Pen is max(OS,OW).

/* ----------  Helper predicates  ------------------------- */

/* choose 2 distinct elements (F1 occurs before F2) from a list */
choose_two(List,F1,F2) :-
        append(_,[F1|Tail],List),
        member(F2,Tail).

/* place the 2 chosen freebies first, preserve order of the rest */
ordered_list(F1,F2,Ordered) :-
        checked_bag_ids(All),
        select(F1,All,Rest1),
        select(F2,Rest1,Rest),
        Ordered = [F1,F2|Rest].

/* compute full cost for one particular choice of freebies */
cost_for_choice(F1,F2,Total) :-
        ordered_list(F1,F2,Ordered),
        cost_bags(Ordered,1,BaseSum,PenSum),
        flight_cost(Flight),
        Total is Flight + BaseSum + PenSum.

/* walk through the ordered list, accumulating costs */
cost_bags([],_,0,0).
cost_bags([Bag|Bs],Idx,BaseSum,PenSum) :-
        (Idx =< 2 -> Type = comp ; Type = charged),
        bag_fee(Idx,BaseFee),
        penalty(Bag,Type,Pen),
        Next is Idx+1,
        cost_bags(Bs,Next,BaseRest,PenRest),
        BaseSum is BaseFee + BaseRest,
        PenSum  is Pen + PenRest.

/* compute minimal total over all possible selections of 2 freebies */
total_cost(MinTotal) :-
        checked_bag_ids(List),
        findall(T,
                (choose_two(List,F1,F2),
                 cost_for_choice(F1,F2,T)),
                Totals),
        min_list(Totals,MinTotal).

/* ----------  Query & output  ---------------------------- */
:- total_cost(Total), format('Total cost: ~w~n',[Total]).
:- halt.