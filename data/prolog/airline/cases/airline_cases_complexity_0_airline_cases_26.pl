/* ----------  Statutory rules we need for this case ---------- */

/* size_sum(+L,+W,+H,-Sum)  */
size_sum(L,W,H,S) :- S is L+W+H.

/* ---------------- Oversize fees (U.S. / Canada routes) ---------------- */
oversize_fee(Size, Fee) :-
    Size =< 62,                       Fee = 0.
oversize_fee(Size, Fee) :-
    Size > 62, Size =< 65,            Fee = 30.
oversize_fee(Size, Fee) :-
    Size > 65, Size =< 115,           Fee = 200.

/* ---------------- Overweight fees (U.S. / Canada routes) -------------- */
overweight_fee(Weight, Fee) :-
    Weight =< 50,                     Fee = 0.
overweight_fee(Weight, Fee) :-
    Weight > 50, Weight =< 53,        Fee = 30.
overweight_fee(Weight, Fee) :-
    Weight > 53, Weight =< 70,        Fee = 100.
overweight_fee(Weight, Fee) :-
    Weight > 70, Weight =< 100,       Fee = 200.

/* ---------------- Base bag fee (Premium Economy, domestic U.S.) ------- */
base_bag_fee(Index, Fee) :-
    Index =< 2,                       % 1st & 2nd bag are complimentary
    Fee = 0.
base_bag_fee(3, 150).
base_bag_fee(Index, 200) :-
    Index >= 4.

/* -------------- Combined fee for an individual checked bag ------------ */
bag_total_fee(Index, L, W, H, Weight, TotalFee) :-
    base_bag_fee(Index, Base),
    size_sum(L,W,H,Size),
    oversize_fee(Size, OverSizeFee),
    overweight_fee(Weight, OverWtFee),
    MaxOver is max(OverSizeFee, OverWtFee),
    TotalFee is Base + MaxOver.

/* ----------  Facts for Patricia's journey and her luggage ------------- */
flight_ticket(233).

/* Checked bags: bag(Index, L, W, H, Weight).  (carry-on not listed) */
bag(1, 41, 16, 16, 78).
bag(2, 34, 15, 14, 64).
bag(3, 37, 18,  9, 66).
bag(4, 42, 28, 19, 67).

/* -----------  Aggregate all bag fees and total trip cost -------------- */
total_bag_fees(Sum) :-
    findall(F,
            ( bag(I,L,W,H,WT),
              bag_total_fee(I,L,W,H,WT,F)
            ),
            Fees),
    sum_list(Fees, Sum).

total_cost(Total) :-
    flight_ticket(T),
    total_bag_fees(BagSum),
    Total is T + BagSum.

/* -------------------------  Query  ------------------------------------ */
:- total_cost(Total), format('Total cost: ~w~n', [Total]).
:- halt.