/* ----------  Statutory rules needed for this case ---------- */

% domestic route (Dallas - Boston)
route(domestic).

% passenger and cabin
passenger(karen).
cabin(karen, mainPlus).   % Main Plus = Main Cabin with 1st-bag fee waived

% bags to be checked: bag(ID, Length, Width, Height, Weight)
bag(1, 52, 31, 24, 67).   % 107 in, 67 lbs
bag(2, 34, 18, 12, 57).   %  64 in, 57 lbs
bag(3, 54, 32, 28, 88).   % 114 in, 88 lbs
bag(4, 53, 27, 28, 59).   % 108 in, 59 lbs

% flight ticket price
ticket_price(242).

/* ----------  Size / weight helpers ---------- */

dimension(L,W,H,Dim) :- Dim is L+W+H.

% ----- oversize fee (domestic) -----
oversize_fee(Dim, 0)      :- Dim =< 62.
oversize_fee(Dim, 30)     :- Dim  > 62, Dim =< 65.
oversize_fee(Dim, 200)    :- Dim  > 65, Dim =< 115.

% ----- overweight fee (domestic) -----
overweight_fee(W, 0)      :- W =< 50.
overweight_fee(W, 30)     :- W  > 50, W =< 53.
overweight_fee(W, 100)    :- W  > 53, W =< 70.
overweight_fee(W, 200)    :- W  > 70, W =< 100.

% choose the higher of the two special-need fees
special_fee(BagID, Fee) :-
    bag(BagID,L,W,H,Weight),
    dimension(L,W,H,Dim),
    oversize_fee(Dim, OverSize),
    overweight_fee(Weight, OverWt),
    max_fee(OverSize, OverWt, Fee).

max_fee(A,B,A) :- A >= B.
max_fee(A,B,B) :- B >  A.

/* ----------  Base checked-bag fees (domestic) ---------- */

% base fee numbers for Main Cabin on domestic flights
main_cabin_base_fee(1, 40).
main_cabin_base_fee(2, 45).
main_cabin_base_fee(3, 150).
main_cabin_base_fee(N, 200) :- N >= 4.

% Main Plus waives the 1st checked-bag base fee
base_fee(BagOrder, mainPlus, 0) :- BagOrder = 1.
base_fee(BagOrder, mainPlus, Fee) :-
    BagOrder  > 1,
    main_cabin_base_fee(BagOrder, Fee).

/* ----------  Totals ---------- */

% sum a list
sum_list([],0).
sum_list([H|T],S) :- sum_list(T,Rest), S is H+Rest.

% total base checked-bag fees for this passenger
base_bag_total(Total) :-
    cabin(karen, mainPlus),
    findall(F,
            (bag(Order,_,_,_,_), base_fee(Order, mainPlus, F)),
            Fs),
    sum_list(Fs, Total).

% total oversize / overweight (special-need) fees
special_total(Total) :-
    findall(F, special_fee(_,F), Fs),
    sum_list(Fs, Total).

% overall cost
total_cost(Total) :-
    ticket_price(Ticket),
    base_bag_total(Base),
    special_total(Special),
    Total is Ticket + Base + Special.

/* ----------  Query ---------- */

:- total_cost(Total), format('Total cost: ~w~n', [Total]).
:- halt.