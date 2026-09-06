:- format("~w~n", ["Label: 3115"]).
/* ==========================================================
   Susan - Chicago (U.S.)  --->  Hong Kong
   Business Class
   ========================================================== */

/* -------- Ticket price ----------------------------------- */
flight_cost(1055).


/* -------- Baggage description ---------------------------- */
/* bag(Id, Length, Width, Height, Weight) -- all dimensions in inches, weight in lbs */
bag(2,37,15,12,66).
bag(3,46,29,27,51).
bag(4,38,20,13,53).
bag(5,40,23,20,62).
bag(6,33,20,12,63).
bag(7,53,34,27,53).
bag(8,46,30,25,65).


/* list of ALL checked-bag Ids (carry-on #1 is omitted)      */
checked_bag_ids([2,3,4,5,6,7,8]).

/* ==========================================================
   Statutory rules applicable to this itinerary
   ========================================================== */

/* ---- Utilities ------------------------------------------ */
dims_sum(L,W,H,S) :- S is L+W+H.

/* ---- Over-SIZE fees  (China / Hong Kong routes) ---------- */
oversize_fee(Sum,Fee) :-
        (  Sum =< 62      -> Fee = 0
        ;  Sum =< 65      -> Fee = 30
        ;  Sum =< 115     -> Fee = 200 ).

/* ---- Over-WEIGHT fees ----------------------------------- */
/* Threshold is 70 lbs for COMPLIMENTARY bags, 50 lbs for CHARGED bags */
overweight_fee(W,Thresh,Fee) :-
        (  W =< Thresh    -> Fee = 0
        ;  W =< 53        -> Fee = 30
        ;  W =< 70        -> Fee = 100
        ;  W =< 100       -> Fee = 200 ).

/* ---- Penalty  (max of oversize vs overweight) ----------- */
penalty(BagId,comp,Pen) :-
        bag(BagId,L,W,H,Weight),
        dims_sum(L,W,H,Sum),
        oversize_fee(Sum,OS),
        overweight_fee(Weight,70,OW),        % complimentary -> 70-lb limit
        Pen is max(OS,OW).

penalty(BagId,charged,Pen) :-
        bag(BagId,L,W,H,Weight),
        dims_sum(L,W,H,Sum),
        oversize_fee(Sum,OS),
        overweight_fee(Weight,50,OW),        % charged bag -> 50-lb limit
        Pen is max(OS,OW).

/* ---- Base checked-bag fee  (Business class, US<->Hong Kong) */
bag_fee(1,0).
bag_fee(2,0).
bag_fee(N,200) :- N>=3.                     % 3rd bag and every bag after

/* ==========================================================
   Cost engine
   ========================================================== */

/* choose two different elements (Free1<Free2) from a list */
choose_two(List,F1,F2) :-
        append(_,[F1|Tail],List),
        member(F2,Tail).

/* re-order list so the 2 freebies occupy positions #1 and #2 */
ordered_list(F1,F2,Ordered) :-
        checked_bag_ids(All),
        select(F1,All,R1),
        select(F2,R1,Remainder),
        Ordered = [F1,F2|Remainder].

/* compute cost for one specific choice of the 2 complimentary bags */
choice_cost(F1,F2,Total) :-
        ordered_list(F1,F2,Ordered),
        bags_cost(Ordered,1,BaseFees,Penalties),
        flight_cost(Tix),
        Total is Tix + BaseFees + Penalties.

/* walk through bags accumulating base fees + penalties      */
bags_cost([],_,0,0).
bags_cost([Bag|Bs],Idx,BaseSum,PenSum) :-
        (Idx =< 2 -> Kind = comp ; Kind = charged),
        bag_fee(Idx,Fee),
        penalty(Bag,Kind,Pen),
        Next is Idx+1,
        bags_cost(Bs,Next,BaseRest,PenRest),
        BaseSum is Fee + BaseRest,
        PenSum  is Pen + PenRest.

/* overall minimum total across all ways of selecting freebies */
total_cost(MinTotal) :-
        checked_bag_ids(L),
        findall(T, (choose_two(L,B1,B2), choice_cost(B1,B2,T)), Totals),
        min_list(Totals,MinTotal).

/* ==========================================================
   Query & output
   ========================================================== */
:- total_cost(Total), format('Total cost: ~w~n', [Total]).
:- halt.