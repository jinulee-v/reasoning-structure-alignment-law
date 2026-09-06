:- format("~w~n", ["Label: 2918"]).
/* =========================================================
   Daniel - Business Class  |  Incheon (ICN) -> Los Angeles (LAX)
   Goal: compute total out-of-pocket cost (ticket + baggage)
   ========================================================= */

/* ------------  GIVEN: ticket price  ---------------------- */
flight_cost(358).


/* ------------  BAGS (id, L, W, H, Weight-lbs) ------------ */
bag(2,37,15,11,98).
bag(3,35,14,14,65).
bag(4,35,18,11,91).
bag(5,36,14,13,56).
bag(6,36,18,16,61).
bag(7,42,20,17,53).
bag(8,44,24,18,53).

/* list of all checked-bag Ids (carry-on #1 is omitted)      */
checked_bag_ids([2,3,4,5,6,7,8]).

/* ------------  STATUTORY SCHEDULES  ---------------------- */

/* (A) oversize - To / from Korea, Japan, China ...            */
oversize_fee(Sum,Fee) :-
        ( Sum =< 62  -> Fee = 0
        ; Sum =< 65  -> Fee = 30
        ; Sum =< 115 -> Fee = 200 ).

/* (B) overweight - To / from Korea, Japan, China ...          */
/* Thresh = 70 lbs for complimentary bags, 50 lbs otherwise  */
overweight_fee(W,Thresh,Fee) :-
        ( W =< Thresh -> Fee = 0
        ; W =< 53     -> Fee = 30
        ; W =< 70     -> Fee = 100
        ; W =< 100    -> Fee = 450 ).

/* (C) checked-bag base fee for Business class on this route */
bag_fee(1,0).
bag_fee(2,0).
bag_fee(N,200) :- N >= 3.

/* ------------  HELPER PREDICATES  ------------------------ */

/* sum of the three dimensions */
dims_sum(L,W,H,Sum) :- Sum is L+W+H.

/* choose any 2 different elements (F1<F2) from a list       */
choose_two(List,A,B) :-
        append(_,[A|Tail],List),
        member(B,Tail).

/* reorder master list so the 2 freebies take positions 1-2  */
ordered_list(F1,F2,Ordered) :-
        checked_bag_ids(All),
        select(F1,All,R1),
        select(F2,R1,R2),
        Ordered = [F1,F2|R2].

/* penalty for one bag (higher of overweight vs oversize)    */
penalty(BagId,Type,Pen) :-
        bag(BagId,L,W,H,Weight),
        dims_sum(L,W,H,Sum),
        oversize_fee(Sum,OS),
        (Type = comp -> Limit = 70 ; Limit = 50),
        overweight_fee(Weight,Limit,OW),
        Pen is max(OS,OW).

/* walk through ordered bags accruing base fees + penalties  */
bags_cost([],_,0,0).
bags_cost([Bag|Rest],Idx,BaseTot,PenTot) :-
        (Idx =< 2 -> Kind = comp ; Kind = charged),
        bag_fee(Idx,BF),
        penalty(Bag,Kind,Pen),
        Next is Idx+1,
        bags_cost(Rest,Next,BT2,PT2),
        BaseTot is BF + BT2,
        PenTot  is Pen + PT2.

/* cost for one particular choice of the two complimentary   */
cost_for_choice(F1,F2,Total) :-
        ordered_list(F1,F2,Ord),
        bags_cost(Ord,1,Base,Pen),
        flight_cost(Tix),
        Total is Tix + Base + Pen.

/* --------  OVERALL MINIMUM TOTAL (best free-bag choice) --- */
total_cost(MinTotal) :-
        checked_bag_ids(L),
        findall(T,
                ( choose_two(L,B1,B2),
                  cost_for_choice(B1,B2,T) ),
                Totals),
        min_list(Totals,MinTotal).

/* --------------------  OUTPUT  ---------------------------- */
:- total_cost(Total), format('Total cost: ~w~n', [Total]).
:- halt.