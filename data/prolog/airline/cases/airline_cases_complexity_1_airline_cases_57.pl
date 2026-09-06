/* ===================================================================
   Mary - Business Class - Orlando (MCO) -> Los Angeles (LAX)
   Domestic itinerary (U.S. - U.S.)

   Goal:  Compute the total amount Mary owes (ticket + all luggage
          charges) under the American Airlines bag-fee statutes.
   ===================================================================*/

/* --------  Ticket price  ------------------------------------------ */
flight_cost(291).

/* --------  Bags  ---------------------------------------------------
   bag(Id, Length, Width, Height, Weight)
   Bag 1 (22*13*7, 7 lb) fits the carry-on limits and is free,   so it
   is NOT listed below.  The remaining items must be checked.       */
bag(2,41,24,22,85).
bag(3,47,33,22,63).
bag(4,38,12,14,57).
bag(5,35,19, 9,87).
bag(6,33,19,13,63).
bag(7,35,19, 9,53).
bag(8,50,32,29,75).

/* ordered list of all checked-bag Ids in the sequence they were
   given (needed to preserve "natural" order after removing freebies)*/
checked_bag_ids([2,3,4,5,6,7,8]).

/* --------  Statutory parameters for this route / cabin ----------- */

/* dimensional sum */
dims_sum(L,W,H,S) :- S is L+W+H.

/* oversize fee - within / between U.S. & Canada                     */
oversize_fee(Sum,Fee) :-
        (  Sum =< 62          -> Fee = 0
        ;  Sum =< 65          -> Fee = 30
        ;  Sum =< 115         -> Fee = 200 ).

/* overweight fee - threshold differs for complimentary vs charged  */
overweight_fee(W,Threshold,Fee) :-
        (  W =< Threshold     -> Fee = 0
        ;  W =< 53            -> Fee = 30
        ;  W =< 70            -> Fee = 100
        ;  W =< 100           -> Fee = 200 ).

/* penalty = higher of oversize vs overweight ---------------------- */
penalty(BagId,comp,Pen) :-
        bag(BagId,L,W,H,Weight),
        dims_sum(L,W,H,Sum),
        oversize_fee(Sum,OS),
        overweight_fee(Weight,70,OW),    % 70-lb allowance for free bags
        Pen is max(OS,OW).

penalty(BagId,charged,Pen) :-
        bag(BagId,L,W,H,Weight),
        dims_sum(L,W,H,Sum),
        oversize_fee(Sum,OS),
        overweight_fee(Weight,50,OW),    % 50-lb allowance for paid bags
        Pen is max(OS,OW).

/* checked-bag base fee - Business Class, domestic ----------------- */
bag_fee(Idx,0)      :- Idx =< 2.          % 1st / 2nd free
bag_fee(3,150).
bag_fee(Idx,200)    :- Idx >= 4.

/* --------  Helper predicates  ------------------------------------ */

/* pick any 2 distinct elements F1<F2 from a list */
choose_two(List,F1,F2) :-
        append(_, [F1|Tail], List),
        member(F2, Tail).

/* build overall checked-bag order putting the 2 freebies first      */
ordered_list(F1,F2,Ordered) :-
        checked_bag_ids(All),
        select(F1,All,Rest1),
        select(F2,Rest1,Rest),
        Ordered = [F1,F2|Rest].

/* walk through ordered list, accumulating base fees + penalties     */
cost_bags([], _, 0, 0).
cost_bags([Bag|Bs], Idx, CostSum, PenSum) :-
        (Idx =< 2 -> Type = comp ; Type = charged),
        bag_fee(Idx,Base),
        penalty(Bag,Type,Pen),
        Next is Idx + 1,
        cost_bags(Bs,Next,RestCost,RestPen),
        CostSum is Base + RestCost,
        PenSum  is Pen  + RestPen.

/* compute total for one particular choice of the 2 complimentary bags */
cost_for_choice(F1,F2,Total) :-
        ordered_list(F1,F2,Ordered),
        cost_bags(Ordered,1,BaseFees,Penalties),
        flight_cost(Tix),
        Total is Tix + BaseFees + Penalties.

/* minimal total over all ways of selecting the 2 free checked bags */
compute_total(MinTotal) :-
        checked_bag_ids(List),
        findall(T,
                ( choose_two(List,F1,F2),
                  cost_for_choice(F1,F2,T) ),
                Totals),
        min_list(Totals,MinTotal).


/* --------  Produce the answer  ----------------------------------- */
:- compute_total(Cost), format('Total cost: ~w~n', [Cost]), halt.