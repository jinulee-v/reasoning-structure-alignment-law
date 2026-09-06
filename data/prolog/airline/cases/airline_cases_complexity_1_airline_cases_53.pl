/* ----------  Statutory rules (extracted subset) ---------- */

% Passenger and itinerary
class(main_plus).                        % Main Plus (Main Cabin^)
route(philadelphia, barcelona).          % U.S.  -> Europe
ticket_cost(236).

/* ----------  Passenger's bags (after removing 1 free carry-on) ---------- */
/* checked_bag(Index, Weight(lbs), Length, Width, Height). */

checked_bag(1, 53, 51, 32, 27).   % 1st checked (oversize & overweight)
checked_bag(2, 57, 37, 15, 12).   % 2nd checked (overweight)
checked_bag(3, 55, 33, 19, 11).   % 3rd checked (overweight)
checked_bag(4, 52, 36, 16, 13).   % 4th checked (light oversize & overweight-1)
checked_bag(5, 52, 36, 15, 14).   % 5th checked (light oversize & overweight-1)
checked_bag(6, 62, 38, 12, 14).   % 6th checked (overweight)
checked_bag(7, 70, 50, 33, 26).   % 7th checked (big oversize & overweight)

/* ----------  Helper predicates ---------- */

linear_dim(L,W,H,S) :- S is L+W+H.

% Oversize fees for U.S. <-> Europe
oversize_fee(Linear, Fee) :-
    ( Linear > 65 -> Fee = 150
    ; Linear > 62 -> Fee = 30
    ;                    Fee = 0).

% Overweight fees for U.S. <-> Europe
overweight_fee(Weight, Fee) :-
    ( Weight > 70 -> fail        % not accepted - not needed here
    ; Weight > 53 -> Fee = 100
    ; Weight > 50 -> Fee = 30
    ;                   Fee = 0).

% Choose the higher of overweight vs. oversize
extra_fee(Weight, Linear, Fee) :-
    overweight_fee(Weight, OW),
    oversize_fee(Linear, OS),
    ( OW >= OS -> Fee = OW ; Fee = OS).

/* Base checked-bag fees (Main Plus gives 2 free) */
base_checked_fee(Index, Fee) :-
    class(main_plus),
    ( Index = 1 ; Index = 2 ),   Fee = 0.
base_checked_fee(3, 200).        % 3rd bag
base_checked_fee(I, 200) :- I >= 4.   % 4th bag and beyond

/* ----------  Per-bag total fee ---------- */
bag_fee(Index, TotalFee) :-
    checked_bag(Index, W, L, B, H),
    linear_dim(L,B,H,Linear),
    base_checked_fee(Index, Base),
    extra_fee(W, Linear, Extra),
    TotalFee is Base + Extra.

/* ----------  Sum of all bag fees ---------- */
bags_total(Sum) :-
    findall(F, bag_fee(_,F), List),
    sum_list(List, Sum).

/* ----------  Grand total ---------- */
total_cost(Total) :-
    ticket_cost(Ticket),
    bags_total(Bags),
    Total is Ticket + Bags.

:- total_cost(Total), format('Total cost: ~w~n', [Total]).
:- halt.