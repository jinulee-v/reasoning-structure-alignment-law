/* -------------  Flight and passenger facts ------------- */
flight(linda, philadelphia, nagoya).          % PHL (U.S.) -> NGO (Japan)
ticket_price(linda, 483).                     % USD
class(linda, basic_economy).

/* -------------  Checked-bag facts (carry-on not listed) ------------- */
/* bag(No, Length, Width, Height, Weight).  Dimensions in inches, weight in lbs */
bag(1, 36, 15, 13, 52).     % luggage box
bag(2, 38, 15, 11, 75).     % backpack
bag(3, 44, 23, 16, 62).     % backpack
bag(4, 38, 13, 13, 59).     % backpack

/* -------------  Region the statutes refer to ------------- */
region(japan).          % "to / from India, China, Japan ... Australia, New Zealand"

/* -------------  Base checked-bag fee rules (Basic Economy, Japan) ------------- */
base_checked_fee(1, 75).      % 1st checked bag  $75
base_checked_fee(2, 100).     % 2nd checked bag $100
base_checked_fee(N, 200) :- N >= 3.   % 3rd, 4th ...  $200 each

/* -------------  Over-weight fee rules (Japan) ------------- */
overweight_fee(W, 0)    :- W =< 50.                       % within allowance
overweight_fee(W, 30)   :- W > 50,  W =< 53.              % 50-53 lb
overweight_fee(W, 100)  :- W > 53, W =< 70.               % 53-70 lb
overweight_fee(W, 450)  :- W > 70, W =< 100.              % 70-100 lb

/* -------------  Over-size fee rules (Japan) ------------- */
oversize_fee(Dim, 0)    :- Dim =< 62.                     % within allowance
oversize_fee(Dim, 30)   :- Dim > 62, Dim =< 65.           % 62-65 in
oversize_fee(Dim, 200)  :- Dim > 65, Dim =< 115.          % 65-115 in

/* -------------  Fee applying when both over-weight & over-size ------------- */
/* "The higher fee between oversize and overweight applies, in addition to the checked bag fee." */
extra_fee(Weight, DimSum, Fee) :-
    overweight_fee(Weight, OW),
    oversize_fee(DimSum,   OS),
    ( OW >= OS -> Fee = OW ; Fee = OS ).

/* -------------  Helper to compute one bag's total cost ------------- */
bag_cost(BagNo, Cost) :-
    bag(BagNo, L, W, H, Weight),
    DimSum is L+W+H,
    base_checked_fee(BagNo, Base),
    extra_fee(Weight, DimSum, Extra),
    Cost is Base + Extra.

/* -------------  Sum of all checked-bag costs ------------- */
total_bag_cost(Sum) :-
    findall(C, (bag(N,_,_,_,_), bag_cost(N,C)), Costs),
    sum_list(Costs, Sum).

/* -------------  Total travel cost (ticket + bags) ------------- */
total_cost(Total) :-
    ticket_price(linda, Ticket),
    total_bag_cost(Bags),
    Total is Ticket + Bags.

/* -------------  Query & printing ------------------------- */
:- total_cost(Total), format('Total cost: ~w~n', [Total]).
:- halt.