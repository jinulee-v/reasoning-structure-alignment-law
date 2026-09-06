/* =========  Statutory rules (extracted subset)  ========= */

/* Ticket */
ticket_price(178).

/* Checked-bag allowance for Main Plus on the route Panama -> U.S.
   - 1st and 2nd checked bags are free (Main Cabin gets 1st free on this route,
     Main Plus adds 1 extra free = 2 free in total).                 */
free_bag(2).
free_bag(3).

/* ----------  Over-weight fees (Panama<->U.S.)  ---------- */
overweight_fee(Weight,Fee) :-
    ( Weight > 70  -> Fee = 200         % 70-100 lb
    ; Weight > 53 -> Fee = 100         % >53-70 lb
    ; Weight > 50 -> Fee = 30          % >50-53 lb
    ; Fee = 0).

/* ----------  Over-size fees (Panama<->U.S.)  ---------- */
oversize_fee(Size,Fee) :-
    ( Size > 65 -> Fee = 150           % >65-115 in
    ; Size > 62 -> Fee = 30            % >62-65 in
    ; Fee = 0).

/* ----------  Base checked-bag fee (after free allowance)  ---------- */
base_bag_fee(Id,Fee) :-
    ( free_bag(Id) -> Fee = 0          % free allowance
    ; Fee = 200).                      % 3rd bag and beyond on this route

/* =========  Case facts  ========= */

/* bag(Id, Weight (lb), Size = L+W+H (in)) */
bag(2, 58, 63).
bag(3, 60, 64).
bag(4, 78, 83).
bag(5, 64, 69).
bag(6, 75,105).
bag(7, 53, 65).
bag(8, 69, 99).

/* =========  Cost calculations  ========= */

bag_extra_fee(Id,Extra) :-                     % higher of overweight / oversize
    bag(Id,Wt,Sz),
    overweight_fee(Wt,OW),
    oversize_fee(Sz,OS),
    ( OW >= OS -> Extra = OW ; Extra = OS).

bag_total_cost(Id,Cost) :-
    base_bag_fee(Id,Base),
    bag_extra_fee(Id,Extra),
    Cost is Base + Extra.

bags_total_cost(Total) :-
    findall(C, (bag(Id,_,_), bag_total_cost(Id,C)), Cs),
    sum_list(Cs,Total).

total_cost(Total) :-
    ticket_price(Tkt),
    bags_total_cost(BagCost),
    Total is Tkt + BagCost.

/* =========  Query ========= */
:- total_cost(Total), format('Total cost: ~w~n', [Total]).
:- halt.