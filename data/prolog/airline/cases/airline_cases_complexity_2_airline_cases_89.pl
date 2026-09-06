/* ---------  Facts describing the passenger and the bags ------------ */

% flight(Type) - the kind of itinerary that drives the fee tables
% Ottawa (Canada)  <-->  Orlando (U.S.)  =>   "within_us_canada"
itinerary(within_us_canada).

% passenger's service class
service_class(first).                % First-Class ticket

% ticket price
ticket_cost(114).                    % US $114 for the seat

% bag(Id, L, W, H, Weight)  - all the items Elizabeth is bringing
bag(1, 21, 14,  8,  5).              % backpack - becomes the single carry-on
bag(2, 44, 28, 17, 95).              % checked
bag(3, 33, 17, 14, 51).              % checked
bag(4, 38, 22, 14, 52).              % checked
bag(5, 40, 22, 14, 97).              % checked
bag(6, 36, 20, 10, 63).              % checked
bag(7, 36, 21, 10, 58).              % checked
bag(8, 51, 30, 30, 76).              % checked
bag(9, 50, 25, 25, 80).              % checked
bag(10,37, 15, 13, 51).              % checked
bag(11,33, 18, 13, 89).              % checked

/* --------------------  Helper predicates  -------------------------- */

% one item is used as the free carry-on (the very first bag fact)
carry_on_id(1).

% checked_bag(Id, IndexAmongChecked)
checked_bag(Id, N) :-
    bag(Id,_,_,_,_),
    \+ carry_on_id(Id),
    % generate a running index 1..10 in order of bag Id
    findall(B, (bag(B,_,_,_,_), \+ carry_on_id(B)), L),
    nth1(N, L, Id).

% linear size in inches
size_inches(Id, S) :-
    bag(Id,L,W,H,_),
    S is L+W+H.

% overweight fee for the "within_us_canada" itinerary
overweight_fee(Id, F) :-
    bag(Id,_,_,_,Wt),
    ( Wt > 70  -> F = 200     % 70-100 lbs
    ; Wt > 53  -> F = 100     % 53-70 lbs
    ; Wt > 50  -> F = 30      % 50-53 lbs
    ;              F = 0 ).

% oversize fee for the "within_us_canada" itinerary
oversize_fee(Id, F) :-
    size_inches(Id,S),
    ( S > 65   -> F = 200     % over 65 - 115 in
    ; S > 62   -> F = 30      % 62 - 65 in
    ;              F = 0 ).

% surcharge for a bag: higher of oversize / overweight
surcharge(Id, Fee) :-
    oversize_fee(Id,O),
    overweight_fee(Id,W),
    ( O >= W   -> Fee = O
    ;             Fee = W ).

/* ----------------  Base checked-bag fee table  ---------------------- */

% base_checked_fee(IndexWithinChecked, Fee)  for First-class, U.S./Canada
base_checked_fee(N, Fee) :-
    ( N = 1 ; N = 2 ) -> Fee = 0  ;                 % 1st & 2nd
    ( N = 3        )  -> Fee = 150 ;                % 3rd
                      Fee = 200.                    % 4th +

/* ------------  Total cost for all checked luggage  ------------------ */

checked_bag_cost(Total) :-
    findall(Cost,
            ( checked_bag(Id,Idx),
              base_checked_fee(Idx,Base),
              surcharge(Id,Extra),
              Cost is Base + Extra ),
            Costs),
    sum_list(Costs, Total).

/* --------------  Grand total to be billed to Elizabeth  ------------- */

total_cost(Grand) :-
    ticket_cost(Ticket),
    checked_bag_cost(Bags),
    Grand is Ticket + Bags.

/* --------------------  Query & output  ------------------------------ */

:- total_cost(Total),
   format('Total cost: ~w~n', [Total]).
:- halt.