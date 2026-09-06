% ---------------  Statutory rules that apply to this case ----------------
:- use_module(library(lists)).

% Cabin and itinerary for Daniel
cabin(main_cabin).
route(us_canada).           % "Between U.S. and Canada"

% ---------------- Checked-bag base fees (Main Cabin, US-Canada) ----------
base_fee(us_canada, main_cabin, 1, 35).      % 1st checked bag
base_fee(us_canada, main_cabin, 2, 45).      % 2nd checked bag
base_fee(us_canada, main_cabin, 3, 150).     % 3rd checked bag
base_fee(us_canada, main_cabin, N, 200) :-   % 4th bag and beyond
    N >= 4.

% ---------------- Oversize fees (US-Canada) ------------------------------
oversize_fee(us_canada, Size, 0)   :- Size =< 62.
oversize_fee(us_canada, Size, 30)  :- Size  > 62, Size =< 65.
oversize_fee(us_canada, Size, 200) :- Size  > 65, Size =< 115.

% ---------------- Overweight fees (US-Canada) ----------------------------
overweight_fee(_, Weight, 0)  :- Weight =< 50.
overweight_fee(_, Weight, 30) :- Weight  > 50, Weight =< 53.
overweight_fee(us_canada, Weight, 100) :- Weight > 53, Weight =< 70.
overweight_fee(us_canada, Weight, 200) :- Weight > 70, Weight =< 100.

% --------------- Helper --------------------------------------------------
max_of_two(A,B,A) :- A>=B, !.
max_of_two(_,B,B).

% --------------- Daniel's bags ------------------------------------------
% bag(Index, Length, Width, Height, Weight).
bag(1, 47,31,23, 52).   % first checked bag
bag(2, 35,16,13, 98).   % second checked bag
bag(3, 40,29,16, 91).   % third checked bag
bag(4, 35,16,14, 86).   % fourth checked bag

% --------------- Fee for each checked bag --------------------------------
bag_fee(Index, Fee) :-
    bag(Index,L,W,H,Weight),
    route(Route), cabin(Cabin),
    Size is L+W+H,
    oversize_fee(Route, Size, OverSizeFee),
    overweight_fee(Route, Weight, OverWtFee),
    max_of_two(OverSizeFee, OverWtFee, ExtraFee),
    base_fee(Route, Cabin, Index, BaseFee),
    Fee is BaseFee + ExtraFee.

% --------------- Total of all checked-bag fees ---------------------------
total_bags_fee(Total) :-
    findall(F, bag_fee(_,F), Fs),
    sumlist(Fs, Total).

% --------------- Flight ticket ------------------------------------------
flight_ticket(283).

% --------------- Grand total --------------------------------------------
total_cost(Total) :-
    flight_ticket(Tk),
    total_bags_fee(Bags),
    Total is Tk + Bags.

% ---------------  Query --------------------------------------------------
:- total_cost(Total), format('Total cost: ~w~n', [Total]).
:- halt.