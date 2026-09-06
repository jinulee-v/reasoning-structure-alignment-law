/* ----------  Statutory rules (relevant excerpt) ---------- */

/* Oversize fee for the route Australia <-> U.S.                */
oversize_fee(L, W, H, Fee) :-
    S is L + W + H,
    ( S =< 62  -> Fee = 0          % within included size
    ; S =< 65  -> Fee = 30         % 62-65 in
    ; S =< 115 -> Fee = 200        % 65-115 in
    ).

/* Over-weight fee for the route Australia <-> U.S.             */
overweight_fee(Weight, Fee) :-
    ( Weight =< 50 -> Fee = 0
    ; Weight =< 53 -> Fee = 30     % 50-53 lbs
    ; Weight =< 70 -> Fee = 100    % 53-70 lbs
    ; Weight =< 100 -> Fee = 200   % 70-100 lbs (not used here)
    ; Weight  > 100 -> Fee = 450   % >100 lbs  (not used here)
    ).

/* Main-Plus checked-bag base fees on this route                */
base_fee(Index, Fee) :-
    ( Index =< 2 -> Fee = 0        % 2 free bags with Main Plus
    ; Index = 3  -> Fee = 200      % 3rd bag
    ; Index  > 3 -> Fee = 200      % 4th+ bags
    ).

/* Highest of oversize / overweight, then add base fee          */
bag_fee(Index, TotalFee) :-
    bag(Index,L,W,H,Weight),
    oversize_fee(L,W,H,OverSize),
    overweight_fee(Weight,OverWt),
    Extra is max(OverSize, OverWt),
    base_fee(Index, Base),
    TotalFee is Base + Extra.

/* Sum all checked-bag fees                                     */
total_bag_fees(Sum) :-
    findall(F, bag_fee(_,F), Fs),
    sum_list(Fs, Sum).

/* ----------  Facts for Mary's itinerary  ---------- */

/* Seven checked pieces (carry-on not listed)                    */
bag(1, 51,28,28, 60).   % size 107", 60 lbs
bag(2, 37,19,11, 60).   % size  67", 60 lbs
bag(3, 46,28,25, 57).   % size  99", 57 lbs
bag(4, 33,21, 9, 53).   % size  63", 53 lbs
bag(5, 51,34,28, 66).   % size 113", 66 lbs
bag(6, 46,34,21, 66).   % size 101", 66 lbs
bag(7, 40,23,17, 51).   % size  80", 51 lbs

/* Flight ticket price                                           */
flight_cost(918).

/* ----------  Total trip cost  ---------- */
total_cost(Total) :-
    total_bag_fees(BagFees),
    flight_cost(Ticket),
    Total is BagFees + Ticket.

/* ----------  Query & output  ---------- */
:- total_cost(T), format('Total cost: ~w~n',[T]).
:- halt.