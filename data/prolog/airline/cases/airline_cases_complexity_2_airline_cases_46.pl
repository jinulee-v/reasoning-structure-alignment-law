:- format("~w~n", ["Label: 4994"]).
/* =========================================================
   Joseph - Business Class      Atlanta (U.S.) -> Wuhan (China)
   Statutory luggage charges - American Airlines (Feb-2024)
   ========================================================= */

/* -------- Ticket price ---------------------------------- */
flight_cost(734).


/* -------- Carry-on -------------------------------------- */
/* Bag 1 fits the carry-on limits so it is excluded from the
   checked-bag computations.  Only the checked pieces (Id 2-11)
   appear below.                                            */


/* -------- Checked bags  (bag(Id,Length,Width,Height,Weight)) */
bag(2,40,23,13, 52).
bag(3,38,12,13, 73).
bag(4,33,21, 9, 73).
bag(5,34,19,12, 82).
bag(6,51,33,31, 69).
bag(7,36,17,11,100).
bag(8,52,31,29, 53).
bag(9,48,29,27, 51).
bag(10,36,15,14,53).
bag(11,36,15,13,56).


/* master list of all checked-bag Ids (10 pieces) */
checked_bag_ids([2,3,4,5,6,7,8,9,10,11]).


/* =========================================================
   Statutory rules that apply to this itinerary
   ========================================================= */

/* sum of the three outside dimensions */
dims_sum(L,W,H,S) :- S is L+W+H.


/* ---------- Oversize fees (route: U.S. <-> China) ---------- */
/*  =<62 in  -> $0      62-65 in -> $30      65-115 in -> $200   */
oversize_fee(Sum,Fee) :-
        (   Sum =< 62      -> Fee = 0
        ;   Sum =< 65      -> Fee = 30
        ;   Sum =< 115     -> Fee = 200 ).


/* ---------- Overweight fees (route: U.S. <-> China) -------- */
/*  (Thresh = 70 lb for complimentary bags, 50 lb for charged)
       =<Thresh        -> $0
       =<53 lb         -> $30
       =<70 lb         -> $100
       =<100 lb        -> $450                                  */
overweight_fee(W,Thresh,Fee) :-
        (   W =< Thresh   -> Fee = 0
        ;   W =< 53       -> Fee = 30
        ;   W =< 70       -> Fee = 100
        ;   W =< 100      -> Fee = 450).


/* ---------- Bag penalties -------------------------------- */
/* The higher of the two (oversize vs. overweight) applies.  */
penalty(BagId,complimentary,Pen) :-
        bag(BagId,L,W,H,Weight),
        dims_sum(L,W,H,Sum),
        oversize_fee(Sum,OS),
        overweight_fee(Weight,70,OW),        % 70-lb limit
        Pen is max(OS,OW).

penalty(BagId,charged,Pen) :-
        bag(BagId,L,W,H,Weight),
        dims_sum(L,W,H,Sum),
        oversize_fee(Sum,OS),
        overweight_fee(Weight,50,OW),        % 50-lb limit
        Pen is max(OS,OW).


/* ---------- Checked-bag base fees (Business Class) -------- */
/*   1st & 2nd -> $0     3rd -> $200     4th+ -> $200            */
bag_fee(1,0).
bag_fee(2,0).
bag_fee(3,200).
bag_fee(N,200) :- N>=4.


/* =========================================================
   Helper predicates (choose which 2 bags get the free slots)
   ========================================================= */

/* pick any 2 distinct elements (F1<F2) from a list */
choose_two(List,F1,F2) :-
        append(_,[F1|Tail],List),
        member(F2,Tail).


/* put the chosen freebies in positions 1 and 2,
   preserving the order of the remaining bags              */
ordered_bag_list(F1,F2,Ordered) :-
        checked_bag_ids(All),
        select(F1,All,Rest1),
        select(F2,Rest1,Rest),
        Ordered = [F1,F2|Rest].


/* accumulate cost for a particular ordering */
cost_for_choice(F1,F2,Total) :-
        ordered_bag_list(F1,F2,Ordered),
        bag_costs(Ordered,1,BaseFees,Penalties),
        flight_cost(Ticket),
        Total is Ticket + BaseFees + Penalties.


/* walk through ordered list, summing base fees and penalties */
bag_costs([],_,0,0).
bag_costs([Bag|Bs],Idx,FeeSum,PenSum) :-
        (  Idx =< 2 -> Class = complimentary
        ;            Class = charged ),
        bag_fee(Idx,Fee),
        penalty(Bag,Class,Pen),
        NextIdx is Idx + 1,
        bag_costs(Bs,NextIdx,FeeRest,PenRest),
        FeeSum is Fee + FeeRest,
        PenSum  is Pen + PenRest.


/* compute the minimal total cost over all ways of assigning
   the 2 complimentary-bag slots                            */
total_cost(MinTotal) :-
        checked_bag_ids(L),
        findall(T,
                ( choose_two(L,F1,F2),
                  cost_for_choice(F1,F2,T) ),
                Totals),
        min_list(Totals,MinTotal).


/* =========================================================
   Query & output
   ========================================================= */
:- total_cost(Total), format('Total cost: ~w~n',[Total]).
:- halt.