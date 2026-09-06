/* -------------  General rules derived from the statutes ------------- */

% oversize_fee(+DimSum, -Fee)
% "To / from Europe" route (our only route in this case)
oversize_fee(Dim, 0  ) :- Dim =< 62, !.                 % within normal size
oversize_fee(Dim, 30 ) :- Dim =< 65, !.                 % 62 - 65 in.
oversize_fee(Dim, 150) :- Dim =< 115, !.                % 65 - 115 in.

% overweight_fee(+Weight, -Fee)
% Only the brackets that appear in the case are coded.
overweight_fee(W, 0  ) :- W =< 50, !.                   % =< 50 lbs
overweight_fee(W, 30 ) :- W =< 53, !.                   % 50 - 53 lbs
overweight_fee(W, 100) :- W =< 70, !.                   % 53 - 70 lbs

% base_fee(+BagIndex, -Fee)
% Premium-Economy, Europe <-> U.S. / Puerto Rico route
base_fee(Index, 0  )   :- Index =< 2, !.                % 1st & 2nd checked bags
base_fee(3,     200)   :- !.                            % 3rd bag
base_fee(Index, 200)   :- Index  > 3.                   % 4th bag and beyond

% checked_bag_cost(+Index, -Cost)
checked_bag_cost(Index, Cost) :-
    bag(Index,L,W,H,Weight),
    DimSum is L+W+H,
    oversize_fee(DimSum, OSize),
    overweight_fee(Weight, OWeight),
    ( OSize >= OWeight -> Surcharge = OSize ; Surcharge = OWeight ),
    base_fee(Index, Base),
    Cost is Base + Surcharge.

% total cost of all checked bags
total_bag_cost(Sum) :-
    findall(C, checked_bag_cost(_,C), Cs),
    sum_list(Cs, Sum).

% ticket price
ticket_price(322).

% grand total
total_cost(Total) :-
    total_bag_cost(Bags),
    ticket_price(Tk),
    Total is Tk + Bags.

/* -------------  Facts taken from the case ------------- */

% bag(Index, Length, Width, Height, Weight).
% (Only the 10 checked pieces - the personal item is free and not listed.)
bag(1, 34, 17, 13, 62).
bag(2, 38, 26, 13, 52).
bag(3, 49, 36, 25, 65).
bag(4, 36, 13, 14, 51).
bag(5, 40, 14, 16, 53).
bag(6, 35, 15, 13, 53).
bag(7, 51, 29, 29, 68).
bag(8, 37, 15, 11, 52).
bag(9, 37, 17, 11, 59).
bag(10,34, 22,  9, 53).

/* -------------  Query to display the answer ------------- */
:- total_cost(Total), format('Total cost: ~w~n', [Total]).
:- halt.