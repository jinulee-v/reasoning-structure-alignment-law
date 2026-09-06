/* ========= Rules derived from the statute ========= */

/* passenger and itinerary facts */
passenger(sarah).
class(main_plus).                     /* Main Plus = Main Cabin + 1 free checked bag */
region(us_domestic).                  /* Portland - San Francisco */

/* flight ticket price */
ticket_price(297).

/* -------------------------------------------------- */
/* The 5 items Sarah is travelling with               */
/* bag(ID, Length, Width, Height, Weight_lbs).        */
bag(1, 18, 11,  8, 10).   /* personal item            */
bag(2, 50, 34, 29, 77).
bag(3, 37, 15, 11, 71).
bag(4, 35, 17, 12, 86).
bag(5, 36, 20,  9, 57).

/* -------------------------------------------------- */
/* Derived properties of each bag                     */

dimsum(ID, Sum) :-
    bag(ID,L,W,H,_),
    Sum is L + W + H.

/* personal item - no fee */
personal_item(ID) :-
    bag(ID,L,W,H,_),
    L =< 18, W =< 14, H =< 8.

/* every non-personal-item is a checked bag */
checked_bag(ID) :-
    bag(ID,_,_,_,_),
    \+ personal_item(ID).

/* list of checked bags in a fixed order */
checked_bag_list(List) :-
    findall(ID, checked_bag(ID), IDs),
    sort(IDs, List).

/* position of a checked bag (1,2,3,...) */
bag_position(ID, Pos) :-
    checked_bag_list(List),
    nth1(Pos, List, ID).

/* ---------------- Base checked-bag fee (Main Plus) ---------------- */
base_checked_fee(Pos, 0)  :- Pos = 1.            /* 1st bag free (Main Plus perk) */
base_checked_fee(Pos, 45) :- Pos = 2.            /* 2nd bag (within US)          */
base_checked_fee(Pos, 150):- Pos = 3.            /* 3rd bag                      */
base_checked_fee(Pos, Fee):- Pos  >= 4, Fee = 200. /* 4th+ bag                     */

/* ---------------- Oversize fee (within U.S.) ---------------- */
oversize_fee(ID, 0) :-
    dimsum(ID, S), S =< 62.
oversize_fee(ID, 30) :-
    dimsum(ID, S), S > 62, S =< 65.
oversize_fee(ID, 200) :-
    dimsum(ID, S), S > 65, S =< 115.

/* ---------------- Over-weight fee (within U.S.) ---------------- */
overweight_fee(ID, 0) :-
    bag(ID,_,_,_,W), W =< 50.
overweight_fee(ID, 30) :-
    bag(ID,_,_,_,W), W  > 50, W =< 53.
overweight_fee(ID, 100) :-
    bag(ID,_,_,_,W), W  > 53, W =< 70.
overweight_fee(ID, 200) :-
    bag(ID,_,_,_,W), W  > 70, W =< 100.

/* extra fee for a bag = the higher of oversize vs overweight */
extra_fee(ID, Fee) :-
    oversize_fee(ID, SFee),
    overweight_fee(ID, WFee),
    ( SFee >= WFee -> Fee = SFee ; Fee = WFee ).

/* ---------------- Fee for each checked bag ---------------- */
checked_bag_total(ID, Total) :-
    bag_position(ID, Pos),
    base_checked_fee(Pos, Base),
    extra_fee(ID, Extra),
    Total is Base + Extra.

/* ---------------- Aggregate costs ---------------- */
total_checked_cost(Sum) :-
    findall(Fee, checked_bag_total(_,Fee), Fees),
    sumlist(Fees, Sum).

total_cost(Total) :-
    ticket_price(Tix),
    total_checked_cost(Checked),
    Total is Tix + Checked.

/* ========= Query ========= */
:- total_cost(Total), format('Total cost: ~w~n', [Total]).
:- halt.