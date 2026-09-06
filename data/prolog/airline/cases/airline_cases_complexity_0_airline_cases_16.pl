/* ===================================================================
   American Airlines bag-fee calculator
   Case: David - Business Class - Portland (PDX) <-> Orlando (MCO)
   =================================================================== */


/* ----------  Ticket ------------------------------------------------ */

flight_cost(207).                 /* price of David's ticket in $ */


/* ----------  Checked bags ----------------------------------------- */
/* bag(Id,Length,Width,Height,Weight) */

bag(1,19,14,8,9).   /* backpack */
bag(2,36,16,13,58). /* luggage box */
bag(3,36,16,13,51). /* luggage box */
bag(4,45,30,20,98). /* luggage box */
bag(5,34,18,12,88). /* backpack */

/* list (constant) of all bag Ids                             */
bag_ids([1,2,3,4,5]).

/* ----------  Statutory rules for this itinerary ------------------- */

/* sum of outside dimensions                                          */
dims_sum(L,W,H,S) :- S is L+W+H.

/* ----------------------------------------------------  Oversize fee */
/* Route: within / between U.S. and Canada (includes PDX-MCO)         */
oversize_fee(Sum,Fee) :-
       (   Sum =< 62      -> Fee = 0
       ;   Sum =< 65      -> Fee = 30
       ;   Sum =< 115     -> Fee = 200 ).

/* ---------------------------------------------------  Overweight fee */
/* Different thresholds for complimentary vs. charged bags            */
/* (Business cabin: 70-lb allowance for complimentary bags)           */
overweight_fee(W,Thresh,Fee) :-
       (   W =< Thresh    -> Fee = 0
       ;   W =< 53        -> Fee = 30
       ;   W =< 70        -> Fee = 100
       ;   W =< 100       -> Fee = 200 ).

/* --------------------------------------------------  Penalty (extra) */
/* "Higher of oversize vs. overweight"                                 */
penalty(BagId,comp,Pen) :-                    /* complimentary bag   */
       bag(BagId,L,W,H,Weight),
       dims_sum(L,W,H,Sum),
       oversize_fee(Sum,OS),
       overweight_fee(Weight,70,OW),          /* 70-lb threshold     */
       Pen is max(OS,OW).

penalty(BagId,charged,Pen) :-                 /* excess-fee bag      */
       bag(BagId,L,W,H,Weight),
       dims_sum(L,W,H,Sum),
       oversize_fee(Sum,OS),
       overweight_fee(Weight,50,OW),          /* 50-lb threshold     */
       Pen is max(OS,OW).

/* ----------------------------------------------  Checked-bag fees   */
/* Business Class - travel within U.S.                                 */
bag_fee(1,0).
bag_fee(2,0).
bag_fee(3,150).
bag_fee(N,200) :- N>=4.

/* ----------  Helper predicates ------------------------------------ */

/* Check if an item can be carried on */
can_carry_on(Id) :-
    bag(Id,L,W,H,_),
    dims_sum(L,W,H,Sum),
    Sum =< 45. % 22+14+9 = 45 for carry-on, but personal item is 18+14+8 = 40
    % Actually, let's check if it fits personal item limits first
    MaxDim is max(L,max(W,H)),
    MaxDim =< 18,
    dims_sum(L,W,H,Sum2),
    Sum2 =< 40.

/* Get checked bags - those that cannot be carried on */
checked_bags(CheckedIds) :-
    bag_ids(AllIds),
    findall(Id, (member(Id,AllIds), \+ can_carry_on(Id)), CheckedIds).

/* choose two different elements (Id1<Id2) from a list                */
choose_two(List,Id1,Id2) :-
       append(_,[Id1|Tail],List),
       member(Id2,Tail).

/* build an ordered list whose first 2 positions are the freebies     */
ordered_list(Free1,Free2,Ordered,CheckedBags) :-
       select(Free1,CheckedBags,R1),
       select(Free2,R1,R2),
       Ordered = [Free1,Free2|R2].

/* walk through ordered list accumulating bag fees & penalties        */
cost_bags([],_,0,0).
cost_bags([Bag|Bs],Idx,FeeSum,PenSum) :-
       (Idx =< 2 -> Kind = comp ; Kind = charged),
       bag_fee(Idx,Fee),
       penalty(Bag,Kind,Pen),
       NextIdx is Idx + 1,
       cost_bags(Bs,NextIdx,FRest,PRest),
       FeeSum is Fee + FRest,
       PenSum is Pen + PRest.

/* compute total for a particular selection of the 2 complimentary bags */
choice_total(F1,F2,Total) :-
       checked_bags(CheckedBags),
       ordered_list(F1,F2,Ordered,CheckedBags),
       cost_bags(Ordered,1,Fees,Penalties),
       flight_cost(Tix),
       Total is Tix + Fees + Penalties.

/* minimal total over all ways of choosing the 2 freebies              */
total_cost(Min) :-
       checked_bags(CheckedBags),
       length(CheckedBags,Len),
       (Len >= 2 ->
           findall(T, (choose_two(CheckedBags,F1,F2), choice_total(F1,F2,T)), Ts),
           min_list(Ts,Min)
       ;
           % If less than 2 checked bags, no choice needed
           cost_bags(CheckedBags,1,Fees,Penalties),
           flight_cost(Tix),
           Min is Tix + Fees + Penalties
       ).

/* ----------  Query & output --------------------------------------- */
compute_total(Cost) :- total_cost(Cost).
:- compute_total(Cost), format('Total cost: ~w~n', [Cost]), halt.