% ------------  Statutory rules (only those relevant to this case) ------------
:- use_module(library(lists)).

% ticket
ticket_cost(197).

% passenger class
class(main_plus).

% --------------------------  John's pieces of luggage ------------------------
% bag(Id, Length, Width, Height, Weight).
bag(bag1, 19, 14,  7,  8).   % carry-on (free)
bag(bag2, 43, 29, 17, 80).   % checked  1
bag(bag3, 46, 31, 24, 73).   % checked  2
bag(bag4, 39, 22, 16,100).   % checked  3
bag(bag5, 35, 20, 13, 71).   % checked  4

% --------------------------  Carry-on decision -------------------------------
carry_on(Bag) :-
    bag(Bag,L,W,H,_),
    L =< 22, W =< 14, H =< 9.

checked_bags(Checked) :-
    findall(B,
            (bag(B,_,_,_,_), \+ carry_on(B)),
            Checked),
    Checked = [bag2,bag3,bag4,bag5].     % Preserved stated order

% ---------------- Base checked-bag fee (route: U.S. <-> Panama) ----------------
% Main Plus = Main Cabin allowance + 1 extra free (max 2 free)
base_checked_fee(Seq, Fee) :-
    ( Seq =< 2 -> Fee = 0          % 1st & 2nd bags free
    ; Seq  =:= 3 -> Fee = 200      % 3rd bag
    ; Seq  >= 4 -> Fee = 200 ).    % 4th bag +

% --------------------------- Oversize / Overweight ---------------------------
oversize_fee(L,W,H,Fee) :-
    Dim is L+W+H,
    ( Dim =< 62  -> Fee = 0
    ; Dim =< 65  -> Fee = 30
    ; Dim =< 115 -> Fee = 150
    ; Dim  > 115 -> Fee = 999999 ).         % not accepted (not reached)

overweight_fee(W,Fee) :-
    ( W =< 50  -> Fee = 0
    ; W =< 53  -> Fee = 30
    ; W =< 70  -> Fee = 100
    ; W =< 100 -> Fee = 200
    ; W  > 100 -> Fee = 999999 ).           % not accepted (not reached)

extra_fee(L,W,H,Weight,Fee) :-
    oversize_fee(L,W,H,OS),
    overweight_fee(Weight,OW),
    Fee is max(OS,OW).

% --------------------------- Fee per checked bag -----------------------------
bag_total_fee(Bag,Seq,Total) :-
    bag(Bag,L,W,H,Weight),
    base_checked_fee(Seq,Base),
    extra_fee(L,W,H,Weight,Extra),
    Total is Base + Extra.

% ---------------------------- Aggregate fees ---------------------------------
bag_fees(Total) :-
    checked_bags(List),
    bag_fees(List,1,0,Total).

bag_fees([],_,Acc,Acc).
bag_fees([B|R],Seq,Acc,Total) :-
    bag_total_fee(B,Seq,F),
    Acc1 is Acc + F,
    Seq1 is Seq + 1,
    bag_fees(R,Seq1,Acc1,Total).

total_cost(Total) :-
    ticket_cost(Ticket),
    bag_fees(Bags),
    Total is Ticket + Bags.

% ----------------------------- Final answer ----------------------------------
:- total_cost(Total), format('Total cost: ~w~n', [Total]).
:- halt.