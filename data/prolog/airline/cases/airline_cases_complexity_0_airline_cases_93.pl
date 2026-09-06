/* ---------- Statutory rules that apply to this case ---------- */

/* base checked-bag fee (Main Cabin, to / from India)            */
base_fee(1, 0).      /* 1st checked bag                            */
base_fee(2, 100).    /* 2nd checked bag                           */
base_fee(3, 200).    /* 3rd checked bag                           */
base_fee(4, 200).    /* 4th checked bag                           */

/* overweight fees (to / from India)                             */
overweight_fee(Weight, 450) :- Weight > 70,  Weight =< 100, !.
overweight_fee(Weight, 100) :- Weight > 53,  Weight =< 70,  !.
overweight_fee(Weight,  30) :- Weight > 50,  Weight =< 53,  !.
overweight_fee(_, 0).

/* oversize fees (to / from India)                               */
oversize_fee(DimSum, 200) :- DimSum > 65,  DimSum =< 115, !.
oversize_fee(DimSum,  30) :- DimSum > 62,  DimSum =< 65,  !.
oversize_fee(_, 0).

/* higher of overweight / oversize                               */
extra_fee(Weight, DimSum, Fee) :-
    overweight_fee(Weight, OW),
    oversize_fee(DimSum, OS),
    (OW >= OS -> Fee = OW ; Fee = OS).

/* ---------- Facts for James's checked items ------------------ */
/* bag(Id, Length, Width, Height, Weight).                       */

bag(1, 41, 19, 14, 98).   /* luggage box 98 lb  41*19*14 in */
bag(2, 38, 16, 11, 67).   /* backpack     67 lb  38*16*11 in */
bag(3, 42, 28, 16, 64).   /* luggage box 64 lb  42*28*16 in */
bag(4, 36, 14, 13, 64).   /* backpack     64 lb  36*14*13 in */

/* ---------- Derived calculations ----------------------------- */

dim_sum(L, W, H, Sum) :- Sum is L + W + H.

/* cost of each checked bag, using the order 1-4 given above     */
bag_cost(Index, Cost) :-
    bag(Index, L, W, H, Weight),
    dim_sum(L, W, H, DimSum),
    base_fee(Index, Base),
    extra_fee(Weight, DimSum, Extra),
    Cost is Base + Extra.

/* total of all checked bags                                     */
bags_total(Total) :-
    findall(C, bag_cost(_, C), Cs),
    sum_list(Cs, Total).

sum_list([], 0).
sum_list([H|T], S) :- sum_list(T, R), S is H + R.

/* flight ticket                                                 */
flight_ticket(430).

/* overall total                                                 */
total_cost(Total) :-
    bags_total(Bags),
    flight_ticket(Tix),
    Total is Bags + Tix.

/* ---------- Query to display the answer ---------------------- */
:- total_cost(Total), format('Total cost: ~w~n', [Total]).
:- halt.